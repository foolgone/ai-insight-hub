"""RAG 批量评测服务（Phase 3C）：创建、重试、取消、聚合、汇总、stale 回收。

执行循环在 ``rag_evaluation_runner``；本模块只做编排与状态，不调用模型。
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rag_judge_agent import RagJudgeAgent, RagJudgePromptError, resolve_prompt_version
from app.core.advisory_lock import AdvisoryLock
from app.core.config import settings
from app.core.exceptions import (
    RagEvaluationConflictError,
    RagEvaluationInvalidError,
    RagEvaluationNotFoundError,
)
from app.core.ownership import assert_owner
from app.core.tenancy import require_tenant, tenant_scope
from app.core.pagination import PaginationParams
from app.models import (
    QaDatasetItem,
    RagEvaluationResult,
    RagEvaluationRun,
    Task,
    User,
)
from app.repositories import qa_dataset as qa_repo
from app.repositories import rag_evaluation as repo
from app.schemas.agents.rag_judge import (
    FAITHFULNESS_STRICT_METRIC,
    JUDGE_SCHEMA_V3,
    RAG_JUDGE_METRICS,
    judge_schema_version,
    metric_version_for_prompt,
)
from app.schemas.rag_evaluation import RagEvaluationCreate

RUN_PENDING = "pending"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_PARTIAL_FAILED = "partial_failed"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"

RETRIEVAL_METRIC_VERSION = "v1"

STOP_TIME_BUDGET = "time_budget_exhausted"
STOP_CANCELLED = "cancelled"

TERMINAL_RUN_STATUSES = (RUN_COMPLETED, RUN_PARTIAL_FAILED, RUN_FAILED, RUN_CANCELLED)


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


now_naive = _now_naive


def metric_version_for(metric_name: str, prompt_version: str | None = None) -> str:
    """指标版本：Judge/派生指标按 Prompt；检索指标始终 v1。"""
    if metric_name in RAG_JUDGE_METRICS or metric_name == FAITHFULNESS_STRICT_METRIC:
        return metric_version_for_prompt(metric_name, prompt_version)
    return RETRIEVAL_METRIC_VERSION


def is_invalid_result(row: RagEvaluationResult) -> bool:
    """A/B invalid 统一识别：status=invalid 或 failed+invalid_reason。"""
    return row.status == "invalid" or (row.status == "failed" and bool(row.invalid_reason))


def is_execution_failed(row: RagEvaluationResult) -> bool:
    """只有 failed 且无 invalid_reason 才是执行失败。"""
    return row.status == "failed" and not row.invalid_reason


def item_bucket(rows: Sequence[RagEvaluationResult]) -> str:
    """Item 状态：failed > invalid > evaluated > skipped（有 row 即非 unprocessed）。"""
    if any(is_execution_failed(row) for row in rows):
        return "failed"
    if any(is_invalid_result(row) for row in rows):
        return "invalid"
    if any(row.status == "evaluated" for row in rows):
        return "evaluated"
    return "skipped"


def judge_prompt_version_of(run: RagEvaluationRun) -> str:
    """Run 的 Judge Prompt 版本；优先 run.judge_config，其次快照；缺失按 v1.0.0。"""
    config = run.judge_config or {}
    snapshot = (run.config_snapshot or {}).get("judge_config") or {}
    return str(config.get("prompt_version") or snapshot.get("prompt_version") or "v1.0.0")


def build_retrieval_config(
    *, adapter: str, top_k: int, precision_mode: str, split: str
) -> dict[str, Any]:
    """Run 的检索配置指纹：Trace 复用要求与当前配置**完全相等**。

    WeKnora 的 KB/Agent/Tenant 不在请求体里，必须显式快照，否则换 KB 后无法识别。
    """
    config: dict[str, Any] = {
        "top_k": top_k,
        "precision_mode": precision_mode,
        "split": split,
    }
    if adapter == "weknora":
        config.update(
            {
                "knowledge_base_id": settings.WEKNORA_KB_ID or None,
                "agent_id": settings.WEKNORA_AGENT_ID or None,
                "tenant_id": settings.WEKNORA_TENANT_ID or None,
            }
        )
    return config


def build_judge_config(
    judge_metrics: Sequence[str], *, prompt_version: str | None = None
) -> dict[str, Any]:
    """当前 Judge 指纹（模型/温度/max_tokens/Prompt SHA/Schema/指标版本）。

    仅用于新建 Run；retry 必须复制父 Run 快照，不得调用本函数。
    """
    if not judge_metrics:
        return {}
    resolved_prompt_version = resolve_prompt_version(prompt_version)
    fingerprints: dict[str, Any] = {}
    for metric in judge_metrics:
        agent = RagJudgeAgent(
            metric, prompt_version=resolved_prompt_version  # type: ignore[arg-type]
        )
        fingerprints[metric] = {
            "agent": agent.config.name,
            "model": settings.DEFAULT_LLM_MODEL,
            "temperature": agent.config.temperature,
            "max_tokens": agent.config.max_tokens,
            "prompt_version": agent.prompt_version,
            "resolved_prompt_version": agent.prompt_version,
            "prompt_sha256": agent.prompt_sha256,
            "schema_version": agent.schema_version,
            "rubric_version": agent.rubric_version,
            "metric_version": agent.metric_version,
        }
    return {
        "model": settings.DEFAULT_LLM_MODEL,
        "temperature": settings.DEFAULT_TEMPERATURE,
        "prompt_version": resolved_prompt_version,
        "schema_version": next((item["schema_version"] for item in fingerprints.values()), None),
        "rubric_version": next((item["rubric_version"] for item in fingerprints.values()), None),
        "metric_versions": {
            metric: fingerprint["metric_version"] for metric, fingerprint in fingerprints.items()
        },
        "metric_fingerprints": fingerprints,
    }


def expected_metrics(run: RagEvaluationRun) -> list[str]:
    snapshot = run.config_snapshot or {}
    metrics = list(snapshot.get("metrics") or [])
    metrics.extend(snapshot.get("judge_metrics") or [])
    derived = list(snapshot.get("derived_metrics") or [])
    if (
        not derived
        and judge_schema_version(judge_prompt_version_of(run)) == JUDGE_SCHEMA_V3
        and "faithfulness" in snapshot.get("judge_metrics", [])
    ):
        derived = [FAITHFULNESS_STRICT_METRIC]
    for metric in derived:
        if metric not in metrics:
            metrics.append(metric)
    return metrics


def precision_mode_of(run: RagEvaluationRun) -> str:
    return str((run.retrieval_config or {}).get("precision_mode") or "at_k")


def top_k_of(run: RagEvaluationRun) -> int:
    return int((run.retrieval_config or {}).get("top_k") or 5)


# --------------------------------------------------------------------------- 创建 / 查询


async def _dataset_bundle(
    session: AsyncSession, *, version_id: uuid.UUID, user: User
) -> tuple[Any, Any]:
    version = await qa_repo.get_version(session, version_id)
    if version is None:
        raise RagEvaluationNotFoundError(details={"version_id": str(version_id)})
    dataset = await qa_repo.get_dataset(session, version.dataset_id)
    if dataset is None:
        raise RagEvaluationNotFoundError(details={"dataset_id": str(version.dataset_id)})
    require_tenant(dataset, user, RagEvaluationNotFoundError)
    assert_owner(dataset.user_id, user)
    return dataset, version


async def create_run(
    session: AsyncSession, *, user: User, payload: RagEvaluationCreate
) -> tuple[RagEvaluationRun, Task]:
    dataset, version = await _dataset_bundle(
        session, version_id=payload.dataset_version_id, user=user
    )
    if version.status != "published":
        raise RagEvaluationConflictError(
            "数据集版本未发布，不能创建评测",
            details={"version_id": str(version.id), "status": version.status},
        )

    all_items = await qa_repo.list_all_items(session, version.id)
    if payload.limit > settings.RAG_EVAL_MAX_ITEMS:
        raise RagEvaluationInvalidError(
            "单次评测条目数超过上限",
            details={
                "limit": payload.limit,
                "max_items": settings.RAG_EVAL_MAX_ITEMS,
            },
        )
    if payload.item_ids:
        wanted = set(payload.item_ids)
        missing = wanted - {item.id for item in all_items}
        if missing:
            raise RagEvaluationInvalidError(
                "item_ids 包含不属于该版本的条目",
                details={"missing": [str(item) for item in missing][:10]},
            )
        candidates = [item for item in all_items if item.id in wanted]
    else:
        candidates = [item for item in all_items if item.split == payload.split]
    if not candidates:
        raise RagEvaluationInvalidError(
            "数据集版本没有可评测条目",
            details={"version_id": str(version.id), "split": payload.split},
        )

    selected = candidates[: payload.limit]
    metrics = list(payload.metrics or []) if payload.execution_mode == "retrieve" else []
    judge_metrics = list(payload.judge_metrics or []) if payload.execution_mode == "query" else []

    retrieval_config = build_retrieval_config(
        adapter=payload.adapter,
        top_k=payload.top_k,
        precision_mode=payload.precision_mode,
        split=payload.split,
    )
    try:
        judge_config = build_judge_config(
            judge_metrics, prompt_version=payload.judge_prompt_version
        )
    except RagJudgePromptError as exc:
        raise RagEvaluationInvalidError(
            "指定的 Judge Prompt 不可用",
            details={
                "judge_prompt_version": payload.judge_prompt_version,
                "error": str(exc)[:500],
            },
        ) from exc
    judge_prompt_version = judge_config.get("prompt_version")
    derived_metrics: list[str] = []
    if (
        judge_schema_version(judge_prompt_version) == JUDGE_SCHEMA_V3
        and "faithfulness" in judge_metrics
    ):
        derived_metrics = [FAITHFULNESS_STRICT_METRIC]

    config_snapshot = {
        "dataset_id": str(dataset.id),
        "dataset_name": dataset.name,
        "dataset_source_type": dataset.source_type,
        "dataset_version_id": str(version.id),
        "dataset_version": version.version,
        "dataset_checksum": version.checksum,
        "execution_mode": payload.execution_mode,
        "adapter": payload.adapter,
        "split": payload.split,
        "limit": payload.limit,
        "metrics": metrics,
        "judge_metrics": judge_metrics,
        "derived_metrics": derived_metrics,
        "metric_versions": {
            metric: metric_version_for(metric, judge_prompt_version)
            for metric in [*metrics, *judge_metrics, *derived_metrics]
        },
        "retrieval_config": retrieval_config,
        "judge_config": judge_config,
        "max_items": settings.RAG_EVAL_MAX_ITEMS,
    }

    run_id = uuid.uuid4()
    task = Task(
        tenant_id=dataset.tenant_id,
        task_type="rag_eval",
        task_name="RAG 批量评测",
        user_id=user.id,
        params={"run_id": str(run_id)},
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()

    run = RagEvaluationRun(
        id=run_id,
        tenant_id=dataset.tenant_id,
        user_id=user.id,
        task_id=task.id,
        attempt=1,
        retry_scope="all",
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        dataset_version_id=version.id,
        dataset_checksum=version.checksum,
        execution_mode=payload.execution_mode,
        adapter=payload.adapter,
        retrieval_config=retrieval_config,
        judge_config=judge_config,
        config_snapshot=config_snapshot,
        item_selection={
            "mode": "all",
            "split": payload.split,
            "item_ids": [str(item.id) for item in selected],
        },
        total_items=len(selected),
        status=RUN_PENDING,
    )
    await repo.add_run(session, run)
    logger.info(
        "rag evaluation created run={} version={} mode={} items={}",
        run.id,
        version.id,
        payload.execution_mode,
        run.total_items,
    )
    return run, task


async def get_run(session: AsyncSession, *, user: User, run_id: uuid.UUID) -> RagEvaluationRun:
    run = await repo.get_run(session, run_id)
    if run is None:
        raise RagEvaluationNotFoundError(details={"run_id": str(run_id)})
    require_tenant(run, user, RagEvaluationNotFoundError)
    assert_owner(run.user_id, user)
    return run


async def list_runs(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID | None,
    dataset_version_id: uuid.UUID | None,
    status: str | None,
    execution_mode: str | None,
    adapter: str | None,
    params: PaginationParams,
) -> tuple[list[RagEvaluationRun], Any]:
    scope = None if user.role == "platform_admin" else user.id
    return await repo.list_runs(
        session,
        user_id=scope,
        tenant_id=tenant_scope(user),
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        status=status,
        execution_mode=execution_mode,
        adapter=adapter,
        parent_run_id=None,
        params=params,
    )


async def list_results(
    session: AsyncSession,
    *,
    user: User,
    run_id: uuid.UUID,
    metric_name: str | None,
    status: str | None,
    dataset_item_id: uuid.UUID | None,
    params: PaginationParams,
) -> tuple[list[RagEvaluationResult], Any]:
    await get_run(session, user=user, run_id=run_id)
    return await repo.list_results(
        session,
        run_id=run_id,
        metric_name=metric_name,
        status=status,
        dataset_item_id=dataset_item_id,
        params=params,
    )


# --------------------------------------------------------------------------- 取消 / 重试


async def cancel_run(session: AsyncSession, *, user: User, run_id: uuid.UUID) -> RagEvaluationRun:
    from app.services import task_service

    run = await get_run(session, user=user, run_id=run_id)
    if run.status in TERMINAL_RUN_STATUSES:
        raise RagEvaluationConflictError("评测已结束，无法取消", details={"status": run.status})
    if run.task_id is not None:
        await task_service.cancel(session, user=user, task_id=run.task_id)
    run.status = RUN_CANCELLED
    run.completed_at = _now_naive()
    await session.flush()
    return run


def _assert_parent_snapshot_available(parent: RagEvaluationRun) -> str:
    """校验父 Run 的 Prompt/Schema/指标版本仍可用；不可用则拒绝 retry。"""
    prompt_version = judge_prompt_version_of(parent)
    snapshot = parent.config_snapshot or {}
    judge_metrics = list(snapshot.get("judge_metrics") or [])
    try:
        fingerprints = (parent.judge_config or {}).get("metric_fingerprints") or {}
        for metric in judge_metrics:
            agent = RagJudgeAgent(metric, prompt_version=prompt_version)
            current_sha = agent.prompt_sha256
            expected_sha = (fingerprints.get(metric) or {}).get("prompt_sha256")
            if expected_sha and expected_sha != current_sha:
                raise RagEvaluationConflictError(
                    "父快照 Prompt 内容已变化，必须新建 Run",
                    details={"metric": metric, "prompt_version": prompt_version},
                )
    except RagJudgePromptError as exc:
        raise RagEvaluationConflictError(
            "父快照不可用，必须新建 Run",
            details={"prompt_version": prompt_version, "error": str(exc)[:500]},
        ) from exc

    expected_schema = judge_schema_version(prompt_version)
    snapshot_schema = (parent.judge_config or {}).get("schema_version") or (
        (snapshot.get("judge_config") or {}).get("schema_version")
    )
    if snapshot_schema and snapshot_schema != expected_schema:
        raise RagEvaluationConflictError(
            "父快照 Schema 不可用，必须新建 Run",
            details={"snapshot_schema": snapshot_schema, "expected_schema": expected_schema},
        )

    expected_versions = snapshot.get("metric_versions") or {}
    for metric in judge_metrics:
        current = metric_version_for(metric, prompt_version)
        recorded = expected_versions.get(metric)
        if recorded and recorded != current:
            raise RagEvaluationConflictError(
                "父快照指标版本不可用，必须新建 Run",
                details={
                    "metric": metric,
                    "snapshot_version": recorded,
                    "current_version": current,
                },
            )
    return prompt_version


def retry_candidates(
    *,
    all_ids: set[uuid.UUID],
    expected: Sequence[str],
    expected_versions: dict[str, str],
    state: dict[uuid.UUID, dict[str, RagEvaluationResult]],
) -> list[uuid.UUID]:
    """Item 级重试候选：任一 invalid 排除整个 Item。"""
    candidates: list[uuid.UUID] = []
    for item_id in all_ids:
        rows = state.get(item_id, {})
        if any(is_invalid_result(row) for row in rows.values()):
            continue
        needs_retry = any(
            metric not in rows
            or is_execution_failed(rows[metric])
            or rows[metric].metric_version != expected_versions[metric]
            for metric in expected
        )
        if needs_retry:
            candidates.append(item_id)
    return sorted(candidates, key=str)


async def retry_run(
    session: AsyncSession, *, user: User, run_id: uuid.UUID
) -> tuple[RagEvaluationRun, Task]:
    parent = await get_run(session, user=user, run_id=run_id)
    if parent.status not in (RUN_COMPLETED, RUN_PARTIAL_FAILED, RUN_FAILED, RUN_CANCELLED):
        raise RagEvaluationConflictError("评测尚未结束，不能重试", details={"status": parent.status})
    existing = await repo.list_child_runs(session, parent.id)
    if existing:
        raise RagEvaluationConflictError(
            "该评测已存在重试运行",
            details={"child_run_id": str(existing[0].id)},
        )

    all_ids = {uuid.UUID(str(item)) for item in (parent.item_selection or {}).get("item_ids", [])}
    retry_prompt_version = _assert_parent_snapshot_available(parent)
    retry_judge = dict(parent.judge_config or {})
    expected = expected_metrics(parent)
    expected_versions = {
        metric: metric_version_for(metric, retry_prompt_version) for metric in expected
    }
    parent_results = await repo.results_for_run(session, parent.id)
    state: dict[uuid.UUID, dict[str, RagEvaluationResult]] = defaultdict(dict)
    for row in parent_results:
        state[row.dataset_item_id][row.metric_name] = row

    candidates = retry_candidates(
        all_ids=all_ids,
        expected=expected,
        expected_versions=expected_versions,
        state=state,
    )
    if not candidates:
        raise RagEvaluationConflictError("没有失败的样本需要重试", details={"run_id": str(parent.id)})

    new_run_id = uuid.uuid4()
    task = Task(
        tenant_id=parent.tenant_id,
        task_type="rag_eval",
        task_name="RAG 批量评测（重试失败）",
        user_id=user.id,
        params={"run_id": str(new_run_id)},
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()

    retry_retrieval = dict(parent.retrieval_config or {})
    retry_snapshot = dict(parent.config_snapshot or {})
    retry_snapshot["retrieval_config"] = retry_retrieval
    retry_snapshot["judge_config"] = retry_judge
    retry_snapshot["metric_versions"] = expected_versions
    if FAITHFULNESS_STRICT_METRIC in expected:
        retry_snapshot["derived_metrics"] = [FAITHFULNESS_STRICT_METRIC]

    run = RagEvaluationRun(
        id=new_run_id,
        tenant_id=parent.tenant_id,
        user_id=user.id,
        task_id=task.id,
        parent_run_id=parent.id,
        attempt=parent.attempt + 1,
        retry_scope="failed_only",
        dataset_id=parent.dataset_id,
        dataset_name=parent.dataset_name,
        dataset_version_id=parent.dataset_version_id,
        dataset_checksum=parent.dataset_checksum,
        execution_mode=parent.execution_mode,
        adapter=parent.adapter,
        retrieval_config=retry_retrieval,
        judge_config=retry_judge,
        config_snapshot=retry_snapshot,
        item_selection={
            "mode": "failed_only",
            "parent_run_id": str(parent.id),
            "item_ids": [str(item) for item in candidates],
        },
        total_items=len(candidates),
        status=RUN_PENDING,
    )
    await repo.add_run(session, run)
    logger.info(
        "rag evaluation retry created run={} parent={} items={}",
        run.id,
        parent.id,
        run.total_items,
    )
    return run, task


# --------------------------------------------------------------------------- 执行辅助


async def select_items(session: AsyncSession, run: RagEvaluationRun) -> list[QaDatasetItem]:
    ids = [uuid.UUID(str(item)) for item in (run.item_selection or {}).get("item_ids", [])]
    if not ids:
        return []
    rows = await session.execute(select(QaDatasetItem).where(QaDatasetItem.id.in_(ids)))
    by_id = {row.id: row for row in rows.scalars().all()}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


async def update_task_progress(
    session: AsyncSession,
    *,
    task: Task | None,
    processed: int,
    total: int,
    step: str,
) -> None:
    if task is None:
        return
    task.progress = min(95, 5 + int(processed / total * 90)) if total else 5
    task.current_step = step
    await session.flush()


# --------------------------------------------------------------------------- 收尾 / 聚合


def build_aggregate(
    run: RagEvaluationRun,
    results: Sequence[RagEvaluationResult],
    *,
    unprocessed_items: int,
) -> dict[str, Any]:
    total = run.total_items
    metrics = expected_metrics(run)
    prompt_version = judge_prompt_version_of(run)
    grouped: dict[str, list[RagEvaluationResult]] = defaultdict(list)
    for row in results:
        grouped[row.metric_name].append(row)

    metrics_payload: dict[str, Any] = {}
    for metric in metrics:
        rows = grouped.get(metric, [])
        evaluated = [row for row in rows if row.status == "evaluated" and row.score is not None]
        skipped = [row for row in rows if row.status == "skipped"]
        invalid = [row for row in rows if is_invalid_result(row)]
        failed = [row for row in rows if is_execution_failed(row)]
        mean = (
            round(
                sum(float(row.score) for row in evaluated if row.score is not None)
                / len(evaluated),
                6,
            )
            if evaluated
            else None
        )
        skip_reasons = Counter(row.skipped_reason or "unknown" for row in skipped)
        payload: dict[str, Any] = {
            "metric_version": metric_version_for(metric, prompt_version),
            "mean": mean,
            "evaluated": len(evaluated),
            "skipped": len(skipped),
            "invalid": len(invalid),
            "failed": len(failed),
            "coverage": round(len(evaluated) / total, 4) if total else 0.0,
            "skip_reasons": dict(skip_reasons),
        }
        if metric == "faithfulness":
            supported_count = sum(
                int((row.details or {}).get("supported_count") or 0) for row in evaluated
            )
            unsupported_count = sum(
                int((row.details or {}).get("unsupported_count") or 0) for row in evaluated
            )
            insufficient_count = sum(
                int((row.details or {}).get("insufficient_evidence_count") or 0)
                for row in evaluated
            )
            denom = supported_count + unsupported_count + insufficient_count
            payload.update(
                {
                    "supported_count": supported_count,
                    "unsupported_count": unsupported_count,
                    "insufficient_count": insufficient_count,
                    "insufficient_ratio": (round(insufficient_count / denom, 6) if denom else None),
                    "all_insufficient_count": sum(
                        1 for row in evaluated if (row.details or {}).get("all_insufficient")
                    ),
                }
            )
        metrics_payload[metric] = payload

    evaluated_items = (
        run.evaluated_items
        if getattr(run, "evaluated_items", None) is not None
        else run.completed_items
    ) or 0
    invalid_items = getattr(run, "invalid_items", 0) or 0
    failed_items = getattr(run, "failed_items", 0) or 0
    skipped_items = getattr(run, "skipped_items", 0) or 0
    processed = evaluated_items + invalid_items + failed_items + skipped_items
    return {
        "dataset_id": str(run.dataset_id) if run.dataset_id else None,
        "dataset_name": run.dataset_name,
        "dataset_version_id": str(run.dataset_version_id),
        "execution_mode": run.execution_mode,
        "adapter": run.adapter,
        "items": {
            "total": total,
            "evaluated": evaluated_items,
            "invalid": invalid_items,
            "failed": failed_items,
            "skipped": skipped_items,
            "unprocessed": unprocessed_items,
            "processed": processed,
            "completed": run.completed_items,
            "completion_rate": round(processed / total, 6) if total else 0.0,
            "success_rate": round(evaluated_items / total, 6) if total else 0.0,
        },
        "metrics": metrics_payload,
    }


async def finalize_run(
    session: AsyncSession, run: RagEvaluationRun, *, stopped_reason: str | None = None
) -> RagEvaluationRun:
    results = await repo.results_for_run(session, run.id)
    expected = expected_metrics(run)
    by_item: dict[uuid.UUID, list[RagEvaluationResult]] = defaultdict(list)
    for row in results:
        by_item[row.dataset_item_id].append(row)

    evaluated_items = 0
    invalid_items = 0
    failed_items = 0
    skipped_items = 0
    for rows in by_item.values():
        bucket = item_bucket(rows)
        if bucket == "failed":
            failed_items += 1
        elif bucket == "invalid":
            invalid_items += 1
        elif bucket == "evaluated":
            evaluated_items += 1
        else:
            skipped_items += 1

    unprocessed = max(0, run.total_items - len(by_item))
    run.evaluated_items = evaluated_items
    run.invalid_items = invalid_items
    run.failed_items = failed_items
    run.skipped_items = skipped_items
    run.unprocessed_items = unprocessed
    run.completed_items = evaluated_items

    # Run 状态：invalid 不是 execution failed；全部执行失败才算 failed。
    expected_total = len(expected) * run.total_items
    execution_failed_results = sum(1 for row in results if is_execution_failed(row))
    invalid_results = sum(1 for row in results if is_invalid_result(row))

    if run.status != RUN_CANCELLED:
        if stopped_reason == STOP_TIME_BUDGET and unprocessed > 0:
            run.status = RUN_PARTIAL_FAILED
            run.error_message = STOP_TIME_BUDGET
        elif run.total_items == 0:
            run.status = RUN_COMPLETED
        elif unprocessed > 0:
            run.status = RUN_PARTIAL_FAILED
        elif expected_total and execution_failed_results >= expected_total:
            run.status = RUN_FAILED
        elif execution_failed_results > 0 or invalid_results > 0:
            run.status = RUN_PARTIAL_FAILED
        else:
            run.status = RUN_COMPLETED
    if run.status != RUN_CANCELLED:
        run.completed_at = _now_naive()
    elif run.completed_at is None:
        run.completed_at = _now_naive()
    run.aggregate = build_aggregate(run, results, unprocessed_items=unprocessed)
    await session.flush()
    logger.info(
        "rag evaluation finalized run={} status={} items={} evaluated={} invalid={} "
        "failed={} skipped={} unprocessed={}",
        run.id,
        run.status,
        run.total_items,
        evaluated_items,
        invalid_items,
        failed_items,
        skipped_items,
        unprocessed,
    )
    return run


# --------------------------------------------------------------------------- 跨 Run 汇总


async def summary(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID | None,
    execution_mode: str | None,
    adapter: str | None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    scope = None if user.role == "platform_admin" else user.id
    runs = await repo.list_runs_for_summary(
        session,
        user_id=scope,
        tenant_id=tenant_scope(user),
        dataset_id=dataset_id,
        execution_mode=execution_mode,
        adapter=adapter,
        limit=limit,
    )
    groups: dict[tuple, dict[str, Any]] = {}
    for run in runs:
        snapshot = run.config_snapshot or {}
        key = (
            str(run.dataset_id) if run.dataset_id else "",
            run.dataset_name,
            str(snapshot.get("dataset_source_type") or ""),
            run.execution_mode,
            run.adapter,
        )
        group = groups.setdefault(
            key,
            {
                "dataset_id": run.dataset_id,
                "dataset_name": run.dataset_name,
                "source_type": snapshot.get("dataset_source_type") or "",
                "execution_mode": run.execution_mode,
                "adapter": run.adapter,
                "run_count": 0,
                "total_items": 0,
                "metrics": {},
            },
        )
        group["run_count"] += 1
        group["total_items"] += run.total_items
        for metric, payload in ((run.aggregate or {}).get("metrics") or {}).items():
            slot = group["metrics"].setdefault(
                (metric, payload.get("metric_version") or ""),
                {
                    "metric_name": metric,
                    "metric_version": payload.get("metric_version") or "",
                    "weighted_sum": 0.0,
                    "evaluated": 0,
                    "skipped": 0,
                    "invalid": 0,
                    "failed": 0,
                    "supported_count": 0,
                    "unsupported_count": 0,
                    "insufficient_count": 0,
                    "all_insufficient_count": 0,
                    "skip_reasons": Counter(),
                },
            )
            if payload.get("mean") is not None:
                slot["weighted_sum"] += float(payload["mean"]) * int(payload["evaluated"])
            slot["evaluated"] += int(payload.get("evaluated") or 0)
            slot["skipped"] += int(payload.get("skipped") or 0)
            slot["invalid"] += int(payload.get("invalid") or 0)
            slot["failed"] += int(payload.get("failed") or 0)
            slot["supported_count"] += int(payload.get("supported_count") or 0)
            slot["unsupported_count"] += int(payload.get("unsupported_count") or 0)
            slot["insufficient_count"] += int(payload.get("insufficient_count") or 0)
            slot["all_insufficient_count"] += int(payload.get("all_insufficient_count") or 0)
            slot["skip_reasons"].update(payload.get("skip_reasons") or {})

    result: list[dict[str, Any]] = []
    for group in groups.values():
        metrics = []
        for slot in group["metrics"].values():
            evaluated = slot["evaluated"]
            mean = round(slot["weighted_sum"] / evaluated, 6) if evaluated else None
            metrics.append(
                {
                    "metric_name": slot["metric_name"],
                    "metric_version": slot["metric_version"],
                    "mean": mean,
                    "evaluated": evaluated,
                    "skipped": slot["skipped"],
                    "invalid": slot["invalid"],
                    "failed": slot["failed"],
                    "coverage": round(evaluated / group["total_items"], 4)
                    if group["total_items"]
                    else 0.0,
                    "insufficient_count": slot["insufficient_count"],
                    "insufficient_ratio": (
                        round(
                            slot["insufficient_count"]
                            / (
                                slot["supported_count"]
                                + slot["unsupported_count"]
                                + slot["insufficient_count"]
                            ),
                            6,
                        )
                        if (
                            slot["supported_count"]
                            + slot["unsupported_count"]
                            + slot["insufficient_count"]
                        )
                        else None
                    ),
                    "all_insufficient_count": slot["all_insufficient_count"],
                    "skip_reasons": dict(slot["skip_reasons"]),
                }
            )
        group["metrics"] = sorted(metrics, key=lambda item: item["metric_name"])
        result.append(group)
    return result


# --------------------------------------------------------------------------- stale 回收


async def recover_stale_runs(session: AsyncSession, *, now: datetime | None = None) -> int:
    """回收心跳超时的 Run。

    先用 **Run 级 advisory lock** 确认 Worker 真的不在了：锁被占用说明 Worker 仍存活
    （只是心跳落后），不得标记 failed，否则会和正在执行的 Worker 互相覆盖。
    抢到锁后再次确认状态/心跳（防止 worker 在查询与抢锁之间正常结束）。
    """
    cutoff = (now or _now_naive()) - timedelta(seconds=settings.RAG_EVAL_STALE_SECONDS)
    stale = await repo.list_stale_runs(session, heartbeat_before=cutoff)
    recovered = 0
    for run in stale:
        lock = AdvisoryLock.for_run(run.id)
        if not await lock.acquire():
            logger.info(
                "rag evaluation stale but still locked, skip run={} last_heartbeat={}",
                run.id,
                run.last_heartbeat_at,
            )
            continue
        try:
            await session.refresh(run)
            if run.status != RUN_RUNNING:
                continue
            if run.last_heartbeat_at is None or run.last_heartbeat_at >= cutoff:
                continue
            run.status = RUN_FAILED
            run.error_message = "stale_worker"
            run.completed_at = _now_naive()
            if run.task_id is not None:
                task = await session.get(Task, run.task_id)
                if task is not None and task.status in ("pending", "running"):
                    task.status = "failed"
                    task.error_message = "worker heartbeat timeout"
                    task.completed_at = _now_naive()
            recovered += 1
            logger.warning(
                "rag evaluation stale run={} last_heartbeat={}",
                run.id,
                run.last_heartbeat_at,
            )
        finally:
            await lock.release()
    await session.flush()
    return recovered


__all__ = [
    "RETRIEVAL_METRIC_VERSION",
    "RUN_CANCELLED",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "RUN_PARTIAL_FAILED",
    "RUN_PENDING",
    "RUN_RUNNING",
    "STOP_CANCELLED",
    "STOP_TIME_BUDGET",
    "TERMINAL_RUN_STATUSES",
    "build_judge_config",
    "build_retrieval_config",
    "build_aggregate",
    "cancel_run",
    "create_run",
    "expected_metrics",
    "finalize_run",
    "get_run",
    "judge_prompt_version_of",
    "list_results",
    "list_runs",
    "metric_version_for",
    "now_naive",
    "precision_mode_of",
    "recover_stale_runs",
    "retry_run",
    "select_items",
    "summary",
    "top_k_of",
    "update_task_progress",
]
