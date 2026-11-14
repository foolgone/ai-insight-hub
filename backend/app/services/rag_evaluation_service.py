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

from app.agents.base import load_prompt_version
from app.agents.rag_judge_agent import PROMPT_DIR as RAG_JUDGE_PROMPT_DIR
from app.core.config import settings
from app.core.exceptions import (
    RagEvaluationConflictError,
    RagEvaluationInvalidError,
    RagEvaluationNotFoundError,
)
from app.core.ownership import assert_owner
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
from app.schemas.agents.rag_judge import RAG_JUDGE_METRIC_VERSION
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


def metric_version_for(metric_name: str) -> str:
    if metric_name in RAG_JUDGE_METRIC_VERSION:
        return RAG_JUDGE_METRIC_VERSION[metric_name]
    return RETRIEVAL_METRIC_VERSION


def expected_metrics(run: RagEvaluationRun) -> list[str]:
    snapshot = run.config_snapshot or {}
    metrics = list(snapshot.get("metrics") or [])
    metrics.extend(snapshot.get("judge_metrics") or [])
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

    retrieval_config = {
        "top_k": payload.top_k,
        "precision_mode": payload.precision_mode,
        "split": payload.split,
    }
    judge_config: dict[str, Any] = {}
    if judge_metrics:
        judge_config = {
            "model": settings.DEFAULT_LLM_MODEL,
            "temperature": settings.DEFAULT_TEMPERATURE,
            "prompt_version": load_prompt_version(RAG_JUDGE_PROMPT_DIR),
            "metric_versions": {
                metric: RAG_JUDGE_METRIC_VERSION[metric] for metric in judge_metrics
            },
        }

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
        "metric_versions": {
            metric: metric_version_for(metric) for metric in [*metrics, *judge_metrics]
        },
        "retrieval_config": retrieval_config,
        "judge_config": judge_config,
        "max_items": settings.RAG_EVAL_MAX_ITEMS,
    }

    run_id = uuid.uuid4()
    task = Task(
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
    scope = None if user.role == "admin" else user.id
    return await repo.list_runs(
        session,
        user_id=scope,
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
    # 选中集 = 有 failed 指标 / 缺指标 / 指标版本过期（无结果也属于缺指标）
    expected = expected_metrics(parent)
    parent_results = await repo.results_for_run(session, parent.id)
    state: dict[uuid.UUID, dict[str, RagEvaluationResult]] = defaultdict(dict)
    for row in parent_results:
        state[row.dataset_item_id][row.metric_name] = row

    candidates: list[uuid.UUID] = []
    for item_id in all_ids:
        rows = state.get(item_id, {})
        needs_retry = any(
            metric not in rows
            or rows[metric].status == "failed"
            or rows[metric].metric_version != metric_version_for(metric)
            for metric in expected
        )
        if needs_retry:
            candidates.append(item_id)
    candidates.sort(key=str)
    if not candidates:
        raise RagEvaluationConflictError("没有失败的样本需要重试", details={"run_id": str(parent.id)})

    new_run_id = uuid.uuid4()
    task = Task(
        task_type="rag_eval",
        task_name="RAG 批量评测（重试失败）",
        user_id=user.id,
        params={"run_id": str(new_run_id)},
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()

    run = RagEvaluationRun(
        id=new_run_id,
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
        retrieval_config=dict(parent.retrieval_config or {}),
        judge_config=dict(parent.judge_config or {}),
        config_snapshot=dict(parent.config_snapshot or {}),
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
    grouped: dict[str, list[RagEvaluationResult]] = defaultdict(list)
    for row in results:
        grouped[row.metric_name].append(row)

    metrics_payload: dict[str, Any] = {}
    for metric in metrics:
        rows = grouped.get(metric, [])
        evaluated = [row for row in rows if row.status == "evaluated" and row.score is not None]
        skipped = [row for row in rows if row.status == "skipped"]
        failed = [row for row in rows if row.status == "failed"]
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
        metrics_payload[metric] = {
            "metric_version": metric_version_for(metric),
            "mean": mean,
            "evaluated": len(evaluated),
            "skipped": len(skipped),
            "failed": len(failed),
            "coverage": round(len(evaluated) / total, 4) if total else 0.0,
            "skip_reasons": dict(skip_reasons),
        }

    return {
        "dataset_id": str(run.dataset_id) if run.dataset_id else None,
        "dataset_name": run.dataset_name,
        "dataset_version_id": str(run.dataset_version_id),
        "execution_mode": run.execution_mode,
        "adapter": run.adapter,
        "items": {
            "total": total,
            "completed": run.completed_items,
            "failed": run.failed_items,
            "skipped": run.skipped_items,
            "unprocessed": unprocessed_items,
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

    failed_items = 0
    skipped_items = 0
    completed_items = 0
    for rows in by_item.values():
        statuses = [row.status for row in rows]
        has_failed = any(status == "failed" for status in statuses)
        all_present = len(rows) >= len(expected)
        if has_failed:
            failed_items += 1
        if all_present and not has_failed and all(status == "skipped" for status in statuses):
            skipped_items += 1
        if all_present and not has_failed:
            completed_items += 1

    unprocessed = max(0, run.total_items - len(by_item))
    run.completed_items = completed_items
    run.skipped_items = skipped_items
    run.failed_items = failed_items

    # Run 状态按**结果粒度**判定（重试也按指标粒度）：
    # 只有所有预期结果都是 failed 才算 failed；存在任一非 failed 结果即 partial_failed。
    expected_total = len(expected) * run.total_items
    failed_results = sum(1 for row in results if row.status == "failed")

    if run.status != RUN_CANCELLED:
        if stopped_reason == STOP_TIME_BUDGET and unprocessed > 0:
            run.status = RUN_PARTIAL_FAILED
            run.error_message = STOP_TIME_BUDGET
        elif run.total_items == 0:
            run.status = RUN_COMPLETED
        elif unprocessed > 0:
            run.status = RUN_PARTIAL_FAILED
        elif failed_results == 0:
            run.status = RUN_COMPLETED
        elif expected_total and failed_results >= expected_total:
            run.status = RUN_FAILED
        else:
            run.status = RUN_PARTIAL_FAILED
    if run.status != RUN_CANCELLED:
        run.completed_at = _now_naive()
    elif run.completed_at is None:
        run.completed_at = _now_naive()
    run.aggregate = build_aggregate(run, results, unprocessed_items=unprocessed)
    await session.flush()
    logger.info(
        "rag evaluation finalized run={} status={} items={} failed={} unprocessed={}",
        run.id,
        run.status,
        run.total_items,
        failed_items,
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
    scope = None if user.role == "admin" else user.id
    runs = await repo.list_runs_for_summary(
        session,
        user_id=scope,
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
                    "failed": 0,
                    "skip_reasons": Counter(),
                },
            )
            if payload.get("mean") is not None:
                slot["weighted_sum"] += float(payload["mean"]) * int(payload["evaluated"])
            slot["evaluated"] += int(payload.get("evaluated") or 0)
            slot["skipped"] += int(payload.get("skipped") or 0)
            slot["failed"] += int(payload.get("failed") or 0)
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
                    "failed": slot["failed"],
                    "coverage": round(evaluated / group["total_items"], 4)
                    if group["total_items"]
                    else 0.0,
                    "skip_reasons": dict(slot["skip_reasons"]),
                }
            )
        group["metrics"] = sorted(metrics, key=lambda item: item["metric_name"])
        result.append(group)
    return result


# --------------------------------------------------------------------------- stale 回收


async def recover_stale_runs(session: AsyncSession, *, now: datetime | None = None) -> int:
    cutoff = (now or _now_naive()) - timedelta(seconds=settings.RAG_EVAL_STALE_SECONDS)
    stale = await repo.list_stale_runs(session, heartbeat_before=cutoff)
    for run in stale:
        run.status = RUN_FAILED
        run.error_message = "stale_worker"
        run.completed_at = _now_naive()
        if run.task_id is not None:
            task = await session.get(Task, run.task_id)
            if task is not None and task.status in ("pending", "running"):
                task.status = "failed"
                task.error_message = "worker heartbeat timeout"
                task.completed_at = _now_naive()
        logger.warning(
            "rag evaluation stale run={} last_heartbeat={}", run.id, run.last_heartbeat_at
        )
    await session.flush()
    return len(stale)


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
    "build_aggregate",
    "cancel_run",
    "create_run",
    "expected_metrics",
    "finalize_run",
    "get_run",
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
