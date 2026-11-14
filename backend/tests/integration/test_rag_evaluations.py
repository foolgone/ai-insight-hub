"""RAG 批量评测集成测试（Phase 3C）。

真实 DB + Mock 适配器/Fake Judge，不访问外部服务。
覆盖：全链路、失败隔离、全部失败、时间预算、取消、重试（按指标复用）、
锁生命周期、数据集篡改、创建校验、汇总、权限。
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition import enqueue
from app.core.advisory_lock import AdvisoryLock, lock_key_for_run
from app.core.config import settings
from app.core.security import hash_password
from app.models import (
    QaDataset,
    QaDatasetItem,
    QaDatasetVersion,
    RagEvaluationResult,
    RagEvaluationRun,
    RagTrace,
    Task,
)
from app.services.rag_evaluation_runner import execute_run
from app.services.rag_evaluation_service import build_judge_config, recover_stale_runs
from app.services.rag_judge_service import JudgeOutcome
from app.services.rag.mock import MockRAGAdapter
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

BASE = "/api/v1/rag/evaluations"
MOCK_CHUNK = "mock-chunk-approval-1"
MOCK_DOC = "mock-doc-approval"


class FlakyAdapter(MockRAGAdapter):
    """查询包含 fail 时抛错（模拟外部失败）。"""

    calls = 0

    async def retrieve(self, query: str, *, config=None):  # noqa: ANN001
        self.calls += 1
        if "fail" in query:
            raise RuntimeError("upstream boom")
        return await super().retrieve(query, config=config)


class SlowAdapter(MockRAGAdapter):
    async def retrieve(self, query: str, *, config=None):  # noqa: ANN001
        await asyncio.sleep(0.08)
        return await super().retrieve(query, config=config)


async def _seed(
    db_session: AsyncSession,
    user,
    *,
    queries: list[str],
    evidence: list[dict[str, Any] | None],
    split: str = "test",
    published: bool = True,
    checksum: str = "checksum-1",
) -> tuple[QaDataset, QaDatasetVersion, list[QaDatasetItem]]:
    dataset = QaDataset(user_id=user.id, name=f"ds-{uuid.uuid4().hex[:8]}", source_type="doc")
    await persist(db_session, dataset)
    version = QaDatasetVersion(
        dataset_id=dataset.id,
        version=1,
        status="published" if published else "draft",
        item_count=len(queries),
        checksum=checksum,
    )
    await persist(db_session, version)
    items: list[QaDatasetItem] = []
    for index, query in enumerate(queries, start=1):
        gold = evidence[index - 1]
        items.append(
            QaDatasetItem(
                version_id=version.id,
                item_key=f"Q{index}",
                query=query,
                gold_answer="标准答案",
                gold_evidence=[gold] if gold else [],
                split=split,
                category="售后",
            )
        )
    await persist(db_session, *items)
    return dataset, version, items


def _evidence_doc() -> dict[str, Any]:
    return {"document_id": MOCK_DOC, "chunk_id": MOCK_CHUNK, "evidence_text": "退款 1-3 天到账"}


def _fake_enqueue():
    """返回唯一 celery id（一个用例内可能入队多次，唯一约束不允许重复）。"""

    def _inner(run_id: str) -> str:
        return f"celery-{uuid.uuid4().hex[:12]}"

    return _inner


async def _create_run(
    client, headers, version: QaDatasetVersion, **overrides: Any
) -> dict[str, Any]:
    payload = {
        "dataset_version_id": str(version.id),
        "execution_mode": "retrieve",
        "adapter": "mock",
        "split": "test",
        **overrides,
    }
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 202, response.text
    return response.json()


async def _get_run(client, headers, run_id: str) -> dict[str, Any]:
    response = await client.get(f"{BASE}/{run_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- 全链路


async def test_full_run_retrieve_mode(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    _, version, _ = await _seed(
        db_session,
        test_user,
        queries=["退款多久到账？", "发票怎么开？", "发货多久？"],
        evidence=[_evidence_doc(), None, {"document_id": "missing-doc"}],
    )
    created = await _create_run(client, auth_headers, version)

    result = await execute_run(db_session, uuid.UUID(created["run_id"]))

    assert result["status"] == "completed"
    run = await _get_run(client, auth_headers, created["run_id"])
    assert run["status"] == "completed"
    assert run["task_status"] == "completed"
    assert run["task_progress"] == 100
    assert run["completed_items"] == 3
    assert run["skipped_items"] == 1
    assert run["failed_items"] == 0
    aggregate = run["aggregate"]
    assert aggregate["items"]["total"] == 3
    assert aggregate["metrics"]["hit_rate"]["evaluated"] == 2
    assert aggregate["metrics"]["hit_rate"]["mean"] == pytest.approx(0.5)
    assert aggregate["metrics"]["context_recall"]["skip_reasons"] == {"gold_evidence_missing": 1}

    results = await client.get(f"{BASE}/{created['run_id']}/results", headers=auth_headers)
    body = results.json()
    assert body["pagination"]["total"] == 12  # 3 条 × 4 指标

    # 幂等：重复投递不产生新结果
    await execute_run(db_session, uuid.UUID(created["run_id"]))
    total = await db_session.scalar(
        select(func.count())
        .select_from(RagEvaluationResult)
        .where(RagEvaluationResult.run_id == uuid.UUID(created["run_id"]))
    )
    assert total == 12


async def test_query_mode_copies_judge_outcomes(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())

    async def fake_judge_trace(session, *, trace, item=None, metrics=None, agent_factory=None):
        return [
            JudgeOutcome(
                metric_name=metric,
                metric_version="v1",
                status="evaluated",
                score=0.8,
                details={"reason": "ok"},
                judge_config={"model": "fake"},
            )
            for metric in (metrics or [])
        ]

    monkeypatch.setattr("app.services.rag_evaluation_runner.judge_trace", fake_judge_trace)
    _, version, _ = await _seed(
        db_session, test_user, queries=["退款多久到账？"], evidence=[_evidence_doc()]
    )
    created = await _create_run(client, auth_headers, version, execution_mode="query")

    await execute_run(db_session, uuid.UUID(created["run_id"]))

    run = await _get_run(client, auth_headers, created["run_id"])
    assert run["status"] == "completed"
    assert run["aggregate"]["metrics"]["faithfulness"]["mean"] == pytest.approx(0.8)
    results = (await client.get(f"{BASE}/{created['run_id']}/results", headers=auth_headers)).json()
    assert {row["metric_name"] for row in results["items"]} == {
        "faithfulness",
        "answer_correctness",
        "answer_relevancy",
    }


# --------------------------------------------------------------------------- 失败隔离 / 全部失败


async def test_single_failure_is_isolated(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    monkeypatch.setattr(
        "app.services.rag_evaluation_runner.build_adapter",
        lambda name=None: FlakyAdapter(),
    )
    _, version, _ = await _seed(
        db_session,
        test_user,
        queries=["退款多久到账？", "fail 的问题"],
        evidence=[_evidence_doc(), _evidence_doc()],
    )
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])

    await execute_run(db_session, uuid.UUID(created["run_id"]))

    run = await _get_run(client, auth_headers, created["run_id"])
    assert run["status"] == "partial_failed"
    assert run["task_status"] == "completed"  # 任务执行完毕 ≠ Run 全部成功
    assert run["failed_items"] == 1
    # 失败是「结果粒度」：该条 2 个指标都失败（hit_rate + 自动补的 precision）
    failures = (
        await client.get(
            f"{BASE}/{created['run_id']}/failures?metric_name=hit_rate",
            headers=auth_headers,
        )
    ).json()
    assert failures["pagination"]["total"] == 1
    assert "trace_failed" in (failures["items"][0]["error_message"] or "")


async def test_all_failures_marks_run_failed(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    monkeypatch.setattr(
        "app.services.rag_evaluation_runner.build_adapter",
        lambda name=None: FlakyAdapter(),
    )
    _, version, _ = await _seed(
        db_session,
        test_user,
        queries=["fail 1", "fail 2"],
        evidence=[_evidence_doc(), _evidence_doc()],
    )
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])

    await execute_run(db_session, uuid.UUID(created["run_id"]))

    run = await _get_run(client, auth_headers, created["run_id"])
    assert run["status"] == "failed"
    assert run["task_status"] == "failed"


# --------------------------------------------------------------------------- 时间预算 / 取消


async def test_time_budget_stops_claiming_items(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    monkeypatch.setattr(
        "app.services.rag_evaluation_runner.build_adapter",
        lambda name=None: SlowAdapter(),
    )
    monkeypatch.setattr(settings, "RAG_EVAL_SOFT_BUDGET_SECONDS", 0.05)
    _, version, _ = await _seed(
        db_session,
        test_user,
        queries=["q1", "q2", "q3"],
        evidence=[_evidence_doc(), _evidence_doc(), _evidence_doc()],
    )
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])

    await execute_run(db_session, uuid.UUID(created["run_id"]))

    run = await _get_run(client, auth_headers, created["run_id"])
    assert run["status"] == "partial_failed"
    assert run["error_message"] == "time_budget_exhausted"
    assert run["aggregate"]["items"]["unprocessed"] >= 1
    assert run["total_items"] == 3
    # 已处理条目的结果保留
    results = (await client.get(f"{BASE}/{created['run_id']}/results", headers=auth_headers)).json()
    assert results["pagination"]["total"] >= 1


async def test_cancel_before_start(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    _, version, _ = await _seed(db_session, test_user, queries=["q1"], evidence=[_evidence_doc()])
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])

    cancel = await client.post(f"{BASE}/{created['run_id']}/cancel", headers=auth_headers)
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    result = await execute_run(db_session, uuid.UUID(created["run_id"]))
    assert result["status"] == "cancelled"


# --------------------------------------------------------------------------- 重试（按指标复用）


async def test_retry_reuses_evaluated_results_and_reruns_failed_metric(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    state = {"fail_relevancy": True}

    async def fake_judge_trace(session, *, trace, item=None, metrics=None, agent_factory=None):
        requested = list(metrics or [])
        fingerprints = build_judge_config(requested)["metric_fingerprints"]
        rows = []
        for metric in requested:
            if metric == "answer_relevancy" and state["fail_relevancy"]:
                rows.append(
                    JudgeOutcome(
                        metric_name=metric,
                        metric_version="v1",
                        status="failed",
                        error_message="judge timeout",
                        judge_config=fingerprints[metric],
                    )
                )
            else:
                rows.append(
                    JudgeOutcome(
                        metric_name=metric,
                        metric_version="v1",
                        status="evaluated",
                        score=0.7,
                        details={"reason": "ok"},
                        judge_config=fingerprints[metric],
                    )
                )
        return rows

    monkeypatch.setattr("app.services.rag_evaluation_runner.judge_trace", fake_judge_trace)
    _, version, _ = await _seed(
        db_session, test_user, queries=["退款多久到账？"], evidence=[_evidence_doc()]
    )
    parent_created = await _create_run(client, auth_headers, version, execution_mode="query")
    await execute_run(db_session, uuid.UUID(parent_created["run_id"]))

    parent = await _get_run(client, auth_headers, parent_created["run_id"])
    assert parent["status"] == "partial_failed"
    parent_results = (
        await client.get(f"{BASE}/{parent_created['run_id']}/results", headers=auth_headers)
    ).json()["items"]
    assert {row["status"] for row in parent_results} == {"evaluated", "failed"}

    state["fail_relevancy"] = False
    retry = await client.post(f"{BASE}/{parent_created['run_id']}/retry", headers=auth_headers)
    assert retry.status_code == 202, retry.text
    child_id = retry.json()["run_id"]
    await execute_run(db_session, uuid.UUID(child_id))

    child = await _get_run(client, auth_headers, child_id)
    assert child["status"] == "completed"
    assert child["parent_run_id"] == parent_created["run_id"]
    assert child["total_items"] == 1

    child_results = (await client.get(f"{BASE}/{child_id}/results", headers=auth_headers)).json()[
        "items"
    ]
    by_metric = {row["metric_name"]: row for row in child_results}
    assert by_metric["faithfulness"]["status"] == "evaluated"
    assert by_metric["faithfulness"]["details"]["reused_from_run_id"] == parent_created["run_id"]
    assert (
        by_metric["answer_correctness"]["details"]["reused_from_run_id"] == parent_created["run_id"]
    )
    assert "reused_from_run_id" not in by_metric["answer_relevancy"]["details"]
    assert by_metric["answer_relevancy"]["status"] == "evaluated"
    # 父 Trace 被复用（不再调用适配器）
    assert by_metric["answer_relevancy"]["details"]["trace_reused"] is True
    assert by_metric["answer_relevancy"]["details"]["source_trace_id"] == str(
        by_metric["faithfulness"]["trace_id"]
    )

    # 父 Run 结果保持不变
    parent_after = (
        await client.get(f"{BASE}/{parent_created['run_id']}/results", headers=auth_headers)
    ).json()["items"]
    assert {row["status"] for row in parent_after} == {"evaluated", "failed"}

    # 已有子 Run → 再次重试 409
    again = await client.post(f"{BASE}/{parent_created['run_id']}/retry", headers=auth_headers)
    assert again.status_code == 409


# --------------------------------------------------------------------------- 锁生命周期


async def test_advisory_lock_lifecycle() -> None:
    run_id = uuid.uuid4()
    assert lock_key_for_run(run_id) == lock_key_for_run(run_id)

    first = AdvisoryLock.for_run(run_id)
    assert await first.acquire() is True
    second = AdvisoryLock.for_run(run_id)
    assert await second.acquire() is False

    await first.release()
    third = AdvisoryLock.for_run(run_id)
    assert await third.acquire() is True
    await third.release()


async def test_different_runs_can_hold_locks_concurrently() -> None:
    first = AdvisoryLock.for_run(uuid.uuid4())
    second = AdvisoryLock.for_run(uuid.uuid4())
    try:
        assert await first.acquire() is True
        assert await second.acquire() is True
    finally:
        await first.release()
        await second.release()


async def test_lock_released_when_connection_drops() -> None:
    """模拟 worker 崩溃：连接关闭后锁自动释放（不需要 unlock）。"""
    run_id = uuid.uuid4()
    crashed = AdvisoryLock.for_run(run_id)
    assert await crashed.acquire() is True

    conn = crashed._conn  # noqa: SLF001 - 测试模拟进程退出
    assert conn is not None
    await conn.close()
    crashed._conn = None

    retry = AdvisoryLock.for_run(run_id)
    assert await retry.acquire() is True
    await retry.release()


# --------------------------------------------------------------------------- 数据集 / 创建校验


async def test_dataset_modified_fails_run(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    _, version, _ = await _seed(db_session, test_user, queries=["q1"], evidence=[_evidence_doc()])
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])

    run_row = await db_session.get(RagEvaluationRun, uuid.UUID(created["run_id"]))
    assert run_row is not None
    run_row.dataset_checksum = "tampered"
    await db_session.flush()

    result = await execute_run(db_session, uuid.UUID(created["run_id"]))
    assert result["status"] == "failed"
    run = await _get_run(client, auth_headers, created["run_id"])
    assert run["error_message"] == "dataset_modified"


async def test_create_rejects_unpublished_and_empty(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    _, draft_version, _ = await _seed(
        db_session,
        test_user,
        queries=["q1"],
        evidence=[_evidence_doc()],
        published=False,
    )
    draft = await client.post(
        BASE,
        headers=auth_headers,
        json={
            "dataset_version_id": str(draft_version.id),
            "execution_mode": "retrieve",
        },
    )
    assert draft.status_code == 409, draft.text

    _, empty_version, _ = await _seed(db_session, test_user, queries=[], evidence=[])
    empty = await client.post(
        BASE,
        headers=auth_headers,
        json={
            "dataset_version_id": str(empty_version.id),
            "execution_mode": "retrieve",
        },
    )
    assert empty.status_code == 400, empty.text


# --------------------------------------------------------------------------- 汇总 / 权限


async def test_create_rejects_limit_above_runtime_max(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    monkeypatch.setattr(settings, "RAG_EVAL_MAX_ITEMS", 1)
    _, version, _ = await _seed(
        db_session,
        test_user,
        queries=["q1", "q2"],
        evidence=[_evidence_doc(), _evidence_doc()],
    )

    response = await client.post(
        BASE,
        headers=auth_headers,
        json={
            "dataset_version_id": str(version.id),
            "execution_mode": "retrieve",
            "limit": 2,
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "RAG_EVALUATION_INVALID"


async def test_summary_groups_runs(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    _, version, _ = await _seed(db_session, test_user, queries=["q1"], evidence=[_evidence_doc()])
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])
    await execute_run(db_session, uuid.UUID(created["run_id"]))

    response = await client.get(f"{BASE}/summary", headers=auth_headers)
    assert response.status_code == 200, response.text
    groups = response.json()["groups"]
    assert len(groups) == 1
    group = groups[0]
    assert group["execution_mode"] == "retrieve"
    assert group["run_count"] == 1
    metrics = {item["metric_name"]: item for item in group["metrics"]}
    assert metrics["hit_rate"]["evaluated"] == 1
    assert metrics["hit_rate"]["mean"] == pytest.approx(1.0)


async def test_permissions(client, auth_headers, test_user, db_session, monkeypatch) -> None:
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    _, version, _ = await _seed(db_session, test_user, queries=["q1"], evidence=[_evidence_doc()])
    created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])

    viewer = UserFactory(role="viewer", password_hash=hash_password("viewer12345"))
    await persist(db_session, viewer)
    login = await client.post(
        "/api/v1/auth/login", json={"email": viewer.email, "password": "viewer12345"}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    blocked = await client.post(
        BASE,
        headers=viewer_headers,
        json={"dataset_version_id": str(version.id), "execution_mode": "retrieve"},
    )
    assert blocked.status_code == 403

    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": other.email, "password": "other12345"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    forbidden = await client.get(f"{BASE}/{created['run_id']}", headers=other_headers)
    assert forbidden.status_code == 403


async def test_recover_stale_runs_marks_task_and_run_failed(test_user, db_session) -> None:
    """心跳超时的 Run 由恢复任务标记 failed(stale_worker)，任务同步失败。"""
    from datetime import datetime, timedelta, timezone

    _, version, _ = await _seed(db_session, test_user, queries=["q1"], evidence=[_evidence_doc()])
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    task = Task(
        task_type="rag_eval",
        task_name="stale",
        user_id=test_user.id,
        params={},
        status="running",
        progress=30,
    )
    await persist(db_session, task)
    run = RagEvaluationRun(
        user_id=test_user.id,
        task_id=task.id,
        dataset_name="stale-ds",
        dataset_version_id=version.id,
        execution_mode="retrieve",
        adapter="mock",
        status="running",
        total_items=1,
        started_at=old,
        last_heartbeat_at=old,
    )
    await persist(db_session, run)

    count = await recover_stale_runs(db_session)
    await db_session.flush()

    assert count == 1
    await db_session.refresh(run)
    await db_session.refresh(task)
    assert run.status == "failed"
    assert run.error_message == "stale_worker"
    assert task.status == "failed"
    assert task.error_message == "worker heartbeat timeout"


async def test_retry_does_not_reuse_when_judge_fingerprint_changes(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    """Prompt/模型参数变了 → 不得复制父 Run 的 evaluated 结果。"""
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    state = {"fail_relevancy": True}

    async def fake_judge_trace(session, *, trace, item=None, metrics=None, agent_factory=None):
        requested = list(metrics or [])
        fingerprints = build_judge_config(requested)["metric_fingerprints"]
        rows = []
        for metric in requested:
            failed = metric == "answer_relevancy" and state["fail_relevancy"]
            rows.append(
                JudgeOutcome(
                    metric_name=metric,
                    metric_version="v1",
                    status="failed" if failed else "evaluated",
                    score=None if failed else 0.6,
                    error_message="judge timeout" if failed else None,
                    details={} if failed else {"reason": "ok"},
                    judge_config=fingerprints[metric],
                )
            )
        return rows

    monkeypatch.setattr("app.services.rag_evaluation_runner.judge_trace", fake_judge_trace)
    _, version, _ = await _seed(
        db_session, test_user, queries=["退款多久到账？"], evidence=[_evidence_doc()]
    )
    parent_created = await _create_run(client, auth_headers, version, execution_mode="query")
    await execute_run(db_session, uuid.UUID(parent_created["run_id"]))
    parent = await _get_run(client, auth_headers, parent_created["run_id"])
    assert parent["status"] == "partial_failed"

    state["fail_relevancy"] = False
    monkeypatch.setattr(settings, "DEFAULT_LLM_MODEL", "another-model")
    retry = await client.post(f"{BASE}/{parent_created['run_id']}/retry", headers=auth_headers)
    assert retry.status_code == 202, retry.text
    child_id = retry.json()["run_id"]
    child = await _get_run(client, auth_headers, child_id)
    assert child["judge_config"]["metric_fingerprints"]["faithfulness"]["model"] == (
        "another-model"
    )

    await execute_run(db_session, uuid.UUID(child_id))
    rows = (await client.get(f"{BASE}/{child_id}/results", headers=auth_headers)).json()["items"]
    assert all("reused_from_run_id" not in row["details"] for row in rows)
    assert {row["status"] for row in rows} == {"evaluated"}


async def test_retry_does_not_reuse_trace_when_retrieval_config_changes(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    """top_k/KB 等检索配置变化 → 不得复用父 Trace。"""
    monkeypatch.setattr(enqueue, "enqueue_rag_evaluation", _fake_enqueue())
    monkeypatch.setattr(
        "app.services.rag_evaluation_runner.build_adapter",
        lambda name=None: FlakyAdapter(),
    )
    _, version, _ = await _seed(
        db_session,
        test_user,
        queries=["退款多久到账？", "fail 的问题"],
        evidence=[_evidence_doc(), _evidence_doc()],
    )
    parent_created = await _create_run(client, auth_headers, version, metrics=["hit_rate"])
    await execute_run(db_session, uuid.UUID(parent_created["run_id"]))
    parent = await _get_run(client, auth_headers, parent_created["run_id"])
    assert parent["status"] == "partial_failed"

    retry = await client.post(f"{BASE}/{parent_created['run_id']}/retry", headers=auth_headers)
    assert retry.status_code == 202, retry.text
    child_id = retry.json()["run_id"]
    child_row = await db_session.get(RagEvaluationRun, uuid.UUID(child_id))
    assert child_row is not None
    child_row.retrieval_config = {**dict(child_row.retrieval_config), "top_k": 9}
    await db_session.flush()

    await execute_run(db_session, uuid.UUID(child_id))
    rows = (await client.get(f"{BASE}/{child_id}/results", headers=auth_headers)).json()["items"]
    by_metric = {row["metric_name"]: row for row in rows}
    assert by_metric["hit_rate"]["details"]["trace_reused"] is False
    # 子 Run 生成了自己的 Trace
    count = await db_session.scalar(
        select(func.count())
        .select_from(RagTrace)
        .where(RagTrace.idempotency_key.like(f"rag_eval:{child_id}:%"))
    )
    assert count == 1


async def test_recover_stale_skips_run_held_by_live_worker(test_user, db_session) -> None:
    """Worker 仍持有 advisory lock 时，stale 回收不得标记失败。"""
    from datetime import datetime, timedelta, timezone

    _, version, _ = await _seed(db_session, test_user, queries=["q1"], evidence=[_evidence_doc()])
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    run = RagEvaluationRun(
        user_id=test_user.id,
        dataset_name="stale-locked",
        dataset_version_id=version.id,
        execution_mode="retrieve",
        adapter="mock",
        status="running",
        total_items=1,
        started_at=old,
        last_heartbeat_at=old,
    )
    await persist(db_session, run)

    lock = AdvisoryLock.for_run(run.id)
    assert await lock.acquire() is True
    try:
        assert await recover_stale_runs(db_session) == 0
        await db_session.refresh(run)
        assert run.status == "running"
    finally:
        await lock.release()

    assert await recover_stale_runs(db_session) == 1
    await db_session.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "stale_worker"
