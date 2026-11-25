"""B-509 / B-510 报告服务与 API 集成测试（文件生成/下载）。"""
from __future__ import annotations

import uuid

import pytest

from app.composition import enqueue
from app.agents.base import AgentResult
from app.models import QaDataset, QaDatasetVersion, RagEvaluationRun, Report
from app.services import report_service
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration


class _FakeAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def generate(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _result(insight_degraded: bool = False) -> AgentResult:
    return AgentResult(
        success=True,
        data={
            "title": "测试报告",
            "report_type": "quality",
            "generated_at": "2025-01-15T10:30:00",
            "summary": "整体质量良好。",
            "sections": [{"title": "概览", "content": "共评估 10 条。"}],
            "highlights": ["平均 86.2"],
            "recommendations": ["补充标准答案"],
            "metadata": {"insight_degraded": insight_degraded},
        },
        metadata={"agent": "report_agent", "version": "v1.0.0"},
        duration=1.0,
        token_usage={"input": 100, "output": 50},
    )


async def _datasource(client, auth_headers, name: str = "report-ds") -> str:
    response = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": name, "type": "customer_service"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _comparison_runs(db_session, user, count: int = 2) -> list[RagEvaluationRun]:
    dataset = QaDataset(user_id=user.id, name=f"cmp-ds-{uuid.uuid4().hex[:8]}", source_type="doc")
    await persist(db_session, dataset)
    version = QaDatasetVersion(
        dataset_id=dataset.id,
        version=1,
        status="published",
        item_count=1,
        checksum=uuid.uuid4().hex,
    )
    await persist(db_session, version)
    runs: list[RagEvaluationRun] = []
    for _ in range(count):
        run = RagEvaluationRun(
            user_id=user.id,
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            dataset_version_id=version.id,
            execution_mode="query",
            adapter="mock",
            retrieval_config={"top_k": 3},
            judge_config={"model": "qwen-flash", "prompt_version": "v1.2.5"},
            config_snapshot={},
            item_selection={},
            total_items=120,
            completed_items=120,
            evaluated_items=120,
            invalid_items=0,
            status="completed",
        )
        await persist(db_session, run)
        runs.append(run)
    return runs


def _comparison_payload(runs: list[RagEvaluationRun], *, same_config: bool = True) -> dict:
    base, target = runs
    side = {
        "dataset_name": base.dataset_name,
        "dataset_version_id": str(base.dataset_version_id),
        "execution_mode": "query",
        "adapter": "mock",
        "top_k": 3,
        "completed_at": "2026-11-25T03:33:00Z",
        "judge_model": "qwen-flash",
        "prompt_version": "v1.2.5",
        "total_items": 120,
        "evaluated_items": 120,
        "invalid_items": 0,
        "failed_items": 0,
        "skipped_items": 0,
        "unprocessed_items": 0,
    }
    case = {
        "dataset_item_id": "item-1",
        "item_key": "P12-001",
        "question": "退款申请提交后多久审批？",
        "verdict": "improved",
        "driver_metric": "answer_relevancy",
        "driver_delta": 0.2,
        "note": "R +0.200",
    }
    return {
        "base": {"run_id": str(base.id), **side},
        "target": {"run_id": str(target.id), **side},
        "metrics": [
            {
                "metric_name": "faithfulness",
                "metric_short": "F",
                "label": "Faithfulness",
                "base": 0.776,
                "target": 0.801,
                "delta": 0.026,
            }
        ],
        "case_summary": {
            "improved": 31,
            "regressed": 32,
            "unchanged": 57,
            "invalid": 0,
            "unprocessed": 0,
            "total": 120,
            "aligned_total": 120,
            "exported_cases": 120,
            "case_truncated": False,
        },
        "top_improved": [case],
        "top_regressed": [
            {**case, "item_key": "P12-002", "verdict": "regressed", "driver_delta": -0.2}
        ],
        "same_config": same_config,
        "compare_url": "/rag-evaluations/compare?base=a&target=b",
    }


def _patch_agent(monkeypatch, result: AgentResult | None = None) -> None:
    monkeypatch.setattr(report_service, "_build_agent", lambda: _FakeAgent(result or _result()))
    monkeypatch.setattr(enqueue, "enqueue_report", lambda report_id: "celery-report")


async def test_markdown_report_lifecycle(client, auth_headers, db_session, monkeypatch) -> None:
    _patch_agent(monkeypatch)
    datasource_id = await _datasource(client, auth_headers)

    created = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "质量报告", "report_type": "quality", "format": "markdown"},
    )
    assert created.status_code == 202, created.text
    report_id = created.json()["id"]
    assert created.json()["status"] == "generating"

    outcome = await report_service.run_report_task(report_id, session=db_session)
    assert outcome["status"] == "completed"

    row = await db_session.get(Report, uuid.UUID(report_id))
    assert row is not None
    assert row.status == "completed"
    assert row.file_size and row.file_size > 0
    assert row.data["summary"] == "整体质量良好。"

    detail = await client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "completed"
    assert detail.json()["view_count"] == 1

    download = await client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert "text/markdown" in download.headers["content-type"]
    assert "质量报告" in download.text

    listed = await client.get(f"/api/v1/datasources/{datasource_id}/reports", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1
    assert listed.json()["items"][0]["format"] == "markdown"

    deleted = await client.delete(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/api/v1/reports/{report_id}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REPORT_NOT_FOUND"


async def test_excel_report_generation(client, auth_headers, db_session, monkeypatch) -> None:
    _patch_agent(monkeypatch)
    datasource_id = await _datasource(client, auth_headers, "report-excel-ds")
    created = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "Excel 报告", "report_type": "quality", "format": "excel"},
    )
    report_id = created.json()["id"]

    outcome = await report_service.run_report_task(report_id, session=db_session)

    assert outcome["status"] == "completed"
    download = await client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert "spreadsheetml" in download.headers["content-type"]
    assert len(download.content) > 0


async def test_pdf_report_generation(client, auth_headers, db_session, monkeypatch) -> None:
    _patch_agent(monkeypatch)
    datasource_id = await _datasource(client, auth_headers, "report-pdf-ds")
    created = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "PDF 报告", "report_type": "quality", "format": "pdf"},
    )
    assert created.status_code == 202, created.text
    report_id = created.json()["id"]

    outcome = await report_service.run_report_task(report_id, session=db_session)

    assert outcome["status"] == "completed"
    download = await client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")
    assert len(download.content) > 1000


async def test_html_rejected_with_specific_code(client, auth_headers) -> None:
    datasource_id = await _datasource(client, auth_headers, "report-invalid-ds")

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "x", "report_type": "quality", "format": "html"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "REPORT_FORMAT_INVALID"

    invalid_type = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "x", "report_type": "unknown", "format": "markdown"},
    )
    assert invalid_type.status_code == 422
    assert invalid_type.json()["error"]["code"] == "REPORT_FORMAT_INVALID"


async def test_comprehensive_insight_degraded_markdown(
    client, auth_headers, db_session, monkeypatch
) -> None:
    _patch_agent(monkeypatch, _result(insight_degraded=True))
    datasource_id = await _datasource(client, auth_headers, "report-comprehensive-ds")
    created = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={
            "title": "综合报告",
            "report_type": "comprehensive",
            "format": "markdown",
        },
    )
    report_id = created.json()["id"]

    await report_service.run_report_task(report_id, session=db_session)

    download = await client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert "暂无洞察数据" in download.text


async def test_report_forbidden_for_other_user(
    client, auth_headers, db_session, monkeypatch
) -> None:
    from app.core.security import hash_password

    _patch_agent(monkeypatch)
    datasource_id = await _datasource(client, auth_headers, "report-403-ds")
    created = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "越权报告", "report_type": "quality", "format": "markdown"},
    )
    report_id = created.json()["id"]
    await report_service.run_report_task(report_id, session=db_session)

    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "other12345"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_report_task_registered() -> None:
    import app.tasks  # noqa: F401 - 触发任务模块注册
    from app.core.celery import celery_app

    assert "tasks.generate_report" in celery_app.tasks


async def test_comparison_report_markdown_without_llm(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    """P1-3b：Run 对比报告走确定性渲染，不调用报告 Agent。"""
    datasource_id = await _datasource(client, auth_headers, "report-compare-ds")
    runs = await _comparison_runs(db_session, test_user)
    monkeypatch.setattr(enqueue, "enqueue_report", lambda report_id: "celery-report")

    def _must_not_run() -> None:
        raise AssertionError("comparison report must not call report agent")

    monkeypatch.setattr(report_service, "_build_agent", _must_not_run)

    created = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={
            "title": "Run 对比报告",
            "report_type": "comprehensive",
            "format": "markdown",
            "config": {"run_comparison": _comparison_payload(runs)},
        },
    )
    assert created.status_code == 202, created.text
    report_id = created.json()["id"]

    outcome = await report_service.run_report_task(report_id, session=db_session)
    assert outcome["status"] == "completed"

    download = await client.get(f"/api/v1/reports/{report_id}/download", headers=auth_headers)
    assert download.status_code == 200
    text = download.text
    assert "## Run 对比" in text
    assert "变好 31 / 变差 32 / 不变 57" in text
    assert "Judge beta 噪声提示" in text
    assert "同配置比较" in text
    assert "P12-001" in text
    assert "导出 CSV / 导出 JSON" in text

    row = await db_session.get(Report, uuid.UUID(report_id))
    assert row is not None
    assert row.data["metadata"]["comparison"] is True
    assert row.data["metadata"]["same_config"] is True


async def test_comparison_report_rejects_other_user_run(
    client, auth_headers, test_user, db_session, monkeypatch
) -> None:
    """跨租户 Run 不能进入报告：创建时直接 404。"""
    from app.core.security import hash_password

    datasource_id = await _datasource(client, auth_headers, "report-compare-403-ds")
    own_runs = await _comparison_runs(db_session, test_user, count=1)
    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    other_runs = await _comparison_runs(db_session, other, count=1)
    monkeypatch.setattr(enqueue, "enqueue_report", lambda report_id: "celery-report")

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={
            "title": "越权对比报告",
            "report_type": "comprehensive",
            "format": "markdown",
            "config": {"run_comparison": _comparison_payload([own_runs[0], other_runs[0]])},
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "RAG_EVALUATION_NOT_FOUND"
