"""RAG 批量评测执行器（Phase 3C）。

职责：advisory lock → 读取 Run → 逐条执行/复用 Trace → 计算指标 → 写结果 → 聚合。
约束：Run 内串行；每条样本一个 savepoint + 独立 commit；时间预算耗尽时停止领取新样本。
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.metrics import (
    MetricResult,
    EvidenceRef,
    RetrievedItem,
    evaluate_retrieval,
    normalize_text,
)
from app.core.advisory_lock import AdvisoryLock
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import QaDatasetItem, RagEvaluationResult, RagEvaluationRun, RagTrace, Task, User
from app.repositories import qa_dataset as qa_repo
from app.repositories import rag_evaluation as repo
from app.repositories import rag_trace as trace_repo
from app.services import rag_evaluation_service as service
from app.services.rag import build_adapter
from app.services.rag import execute as rag_execute
from app.services.rag_judge_service import judge_trace
from app.application import task_control

STOP_TIME_BUDGET = service.STOP_TIME_BUDGET


def _trace_contexts(trace: RagTrace) -> list[str]:
    contexts: list[str] = []
    for item in trace.retrieved_contexts or []:
        content = str(item.get("content") or "").strip()
        if content:
            contexts.append(content)
    return contexts


def _retrieved_items(trace: RagTrace) -> list[RetrievedItem]:
    items: list[RetrievedItem] = []
    for index, item in enumerate(trace.retrieved_contexts or [], start=1):
        items.append(
            RetrievedItem(
                content=str(item.get("content") or ""),
                document_id=item.get("document_id"),
                chunk_id=item.get("chunk_id"),
                rank=item.get("rank") or index,
            )
        )
    return items


def _gold_evidence(item: QaDatasetItem) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for entry in item.gold_evidence or []:
        refs.append(
            EvidenceRef(
                document_id=entry.get("document_id"),
                chunk_id=entry.get("chunk_id"),
                text=entry.get("evidence_text"),
            )
        )
    return refs


def _trace_reusable(trace: RagTrace, run: RagEvaluationRun, item: QaDatasetItem) -> bool:
    if trace.status != "success":
        return False
    if trace.adapter != run.adapter or trace.mode != run.execution_mode:
        return False
    if trace.dataset_item_id != item.id:
        return False
    return dict(trace.retrieval_config or {}) == dict(run.retrieval_config or {})


async def _resolve_trace(
    session: AsyncSession,
    *,
    run: RagEvaluationRun,
    item: QaDatasetItem,
    adapter: Any,
    user: User,
) -> tuple[RagTrace, bool]:
    if run.parent_run_id is not None:
        parent_key = f"rag_eval:{run.parent_run_id}:{item.id}"
        parent_trace = await trace_repo.get_by_idempotency_key(session, parent_key)
        if parent_trace is not None and _trace_reusable(parent_trace, run, item):
            return parent_trace, True

    key = f"rag_eval:{run.id}:{item.id}"
    existing = await trace_repo.get_by_idempotency_key(session, key)
    if existing is not None:
        return existing, False

    trace = await rag_execute.execute_query(
        session,
        user=user,
        adapter=adapter,
        query=item.query,
        mode=run.execution_mode,  # type: ignore[arg-type]
        dataset_item_id=item.id,
        config=run.retrieval_config,
        task_id=run.task_id,
        idempotency_key=key,
    )
    return trace, False


def _evidence_verified(
    claims: Sequence[Mapping[str, Any]], contexts: Sequence[str]
) -> dict[str, int]:
    normalized = [text for text in (normalize_text(ctx) for ctx in contexts) if text]
    verified = 0
    for claim in claims:
        for evidence in claim.get("evidence") or []:
            candidate = normalize_text(str(evidence))
            if candidate and any(candidate in ctx for ctx in normalized):
                verified += 1
                break
    return {"claims": len(claims), "verified": verified}


def _row_from_metric(
    *,
    run: RagEvaluationRun,
    item: QaDatasetItem,
    trace: RagTrace,
    metric: str,
    result: MetricResult,
    trace_reused: bool,
) -> RagEvaluationResult:
    details = dict(result.details or {})
    details["trace_reused"] = trace_reused
    if trace_reused:
        details["source_trace_id"] = str(trace.id)
    return RagEvaluationResult(
        run_id=run.id,
        dataset_item_id=item.id,
        trace_id=trace.id,
        metric_name=metric,
        metric_version=service.metric_version_for(metric),
        status=result.status,
        score=result.value,
        skipped_reason=result.skipped_reason,
        details=details,
        judge_config={},
        latency_ms=None,
    )


def _failed_row(
    *,
    run: RagEvaluationRun,
    item: QaDatasetItem,
    metric: str,
    error: str,
    trace_id: uuid.UUID | None = None,
    trace_reused: bool = False,
) -> RagEvaluationResult:
    return RagEvaluationResult(
        run_id=run.id,
        dataset_item_id=item.id,
        trace_id=trace_id,
        metric_name=metric,
        metric_version=service.metric_version_for(metric),
        status="failed",
        score=None,
        details={"error": error[:1000], "trace_reused": trace_reused},
        judge_config={},
        error_message=error[:2000],
    )


def _copy_parent_result(
    *, run: RagEvaluationRun, item: QaDatasetItem, parent: RagEvaluationResult
) -> RagEvaluationResult:
    details = dict(parent.details or {})
    details["reused_from_run_id"] = str(parent.run_id)
    details["reused_result_id"] = str(parent.id)
    return RagEvaluationResult(
        run_id=run.id,
        dataset_item_id=item.id,
        trace_id=parent.trace_id,
        metric_name=parent.metric_name,
        metric_version=parent.metric_version,
        status=parent.status,
        score=parent.score,
        skipped_reason=parent.skipped_reason,
        details=details,
        judge_config=dict(parent.judge_config or {}),
        raw_output=parent.raw_output,
        raw_truncated=parent.raw_truncated,
        latency_ms=parent.latency_ms,
        error_message=parent.error_message,
    )


async def _evaluate_trace(
    session: AsyncSession,
    *,
    run: RagEvaluationRun,
    item: QaDatasetItem,
    trace: RagTrace,
    metrics: Sequence[str],
    judge_metrics: Sequence[str],
    trace_reused: bool,
) -> list[RagEvaluationResult]:
    rows: list[RagEvaluationResult] = []

    if metrics:
        retrieved = _retrieved_items(trace)
        gold = _gold_evidence(item)
        outcome = evaluate_retrieval(
            retrieved,
            gold,
            k=service.top_k_of(run),
            precision_mode=service.precision_mode_of(run),  # type: ignore[arg-type]
        )
        for metric in metrics:
            result = outcome.get(metric)
            if result is None:
                rows.append(
                    _failed_row(
                        run=run,
                        item=item,
                        metric=metric,
                        error="metric_not_computed",
                        trace_id=trace.id,
                        trace_reused=trace_reused,
                    )
                )
            else:
                rows.append(
                    _row_from_metric(
                        run=run,
                        item=item,
                        trace=trace,
                        metric=metric,
                        result=result,
                        trace_reused=trace_reused,
                    )
                )

    if judge_metrics:
        outcomes = await judge_trace(
            session, trace=trace, item=item, metrics=list(judge_metrics)  # type: ignore[arg-type]
        )
        by_metric = {row.metric_name: row for row in outcomes}
        contexts = _trace_contexts(trace)
        for metric in judge_metrics:
            judge = by_metric.get(metric)
            if judge is None:
                rows.append(
                    _failed_row(
                        run=run,
                        item=item,
                        metric=metric,
                        error="metric_not_computed",
                        trace_id=trace.id,
                        trace_reused=trace_reused,
                    )
                )
                continue
            details = dict(judge.details or {})
            details["trace_reused"] = trace_reused
            if trace_reused:
                details["source_trace_id"] = str(trace.id)
            if metric == "faithfulness" and judge.status == "evaluated":
                details["evidence_verified"] = _evidence_verified(
                    details.get("claims") or [], contexts
                )
            rows.append(
                RagEvaluationResult(
                    run_id=run.id,
                    dataset_item_id=item.id,
                    trace_id=trace.id,
                    metric_name=metric,
                    metric_version=judge.metric_version,
                    status=judge.status,
                    score=judge.score,
                    skipped_reason=judge.skipped_reason,
                    details=details,
                    judge_config=dict(judge.judge_config or {}),
                    raw_output=judge.raw_output,
                    raw_truncated=judge.raw_truncated,
                    latency_ms=judge.latency_ms,
                    error_message=judge.error_message,
                )
            )
    return rows


async def _process_item(
    session: AsyncSession,
    *,
    run: RagEvaluationRun,
    item: QaDatasetItem,
    adapter: Any,
    user: User,
    metrics: Sequence[str],
    judge_metrics: Sequence[str],
) -> None:
    started = time.monotonic()
    expected = [*metrics, *judge_metrics]

    parent_results: dict[str, RagEvaluationResult] = {}
    if run.parent_run_id is not None:
        rows = await repo.results_for_item(
            session, run_id=run.parent_run_id, dataset_item_id=item.id
        )
        parent_results = {row.metric_name: row for row in rows}

    to_execute: list[str] = []
    ready: list[RagEvaluationResult] = []
    for metric in expected:
        parent = parent_results.get(metric)
        if (
            parent is not None
            and parent.status in ("evaluated", "skipped")
            and parent.metric_version == service.metric_version_for(metric)
        ):
            ready.append(_copy_parent_result(run=run, item=item, parent=parent))
        else:
            to_execute.append(metric)

    if to_execute:
        try:
            async with session.begin_nested():
                trace, reused = await _resolve_trace(
                    session, run=run, item=item, adapter=adapter, user=user
                )
                if trace.status != "success":
                    for metric in to_execute:
                        ready.append(
                            _failed_row(
                                run=run,
                                item=item,
                                metric=metric,
                                error=f"trace_failed: {trace.error_message or 'unknown'}",
                                trace_id=trace.id,
                            )
                        )
                else:
                    ready.extend(
                        await _evaluate_trace(
                            session,
                            run=run,
                            item=item,
                            trace=trace,
                            metrics=[m for m in to_execute if m in metrics],
                            judge_metrics=[m for m in to_execute if m in judge_metrics],
                            trace_reused=reused,
                        )
                    )
                latency = int((time.monotonic() - started) * 1000)
                for row in ready:
                    row.details = {**(row.details or {}), "item_latency_ms": latency}
                await repo.add_results_ignore_conflicts(session, ready)
        except Exception as exc:  # noqa: BLE001 - 单条失败隔离
            logger.opt(exception=exc).warning(
                "rag evaluation item failed run={} item={}", run.id, item.id
            )
            latency = int((time.monotonic() - started) * 1000)
            failed = [
                _failed_row(
                    run=run,
                    item=item,
                    metric=metric,
                    error=f"{type(exc).__name__}: {exc}",
                )
                for metric in expected
            ]
            for row in failed:
                row.details = {**(row.details or {}), "item_latency_ms": latency}
            await repo.add_results_ignore_conflicts(session, failed)
    else:
        latency = int((time.monotonic() - started) * 1000)
        for row in ready:
            row.details = {**(row.details or {}), "item_latency_ms": latency}
        await repo.add_results_ignore_conflicts(session, ready)


async def _verify_dataset(session: AsyncSession, run: RagEvaluationRun) -> bool:
    version = await qa_repo.get_version(session, run.dataset_version_id)
    if version is None:
        return False
    return (version.checksum or "") == (run.dataset_checksum or "")


async def execute_run(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any]:
    """在给定 session 上执行（Celery 用 SessionLocal，测试可注入）。"""
    run = await repo.get_run(session, run_id)
    if run is None:
        return {"status": "missing", "run_id": str(run_id)}
    if run.status in service.TERMINAL_RUN_STATUSES:
        return {"status": run.status, "run_id": str(run_id)}

    task = await session.get(Task, run.task_id) if run.task_id else None

    if not await _verify_dataset(session, run):
        run.status = service.RUN_FAILED
        run.error_message = "dataset_modified"
        run.completed_at = service._now_naive()
        if task is not None:
            task.status = "failed"
            task.error_message = "dataset_modified"
            task.completed_at = service._now_naive()
        await session.commit()
        return {"status": run.status, "run_id": str(run_id)}

    run.status = service.RUN_RUNNING
    run.started_at = service._now_naive()
    run.last_heartbeat_at = service._now_naive()
    if task is not None:
        task.status = "running"
        task.started_at = service._now_naive()
        task.current_step = "starting"
    await session.commit()

    user = await session.get(User, run.user_id)
    if user is None:
        run.status = service.RUN_FAILED
        run.error_message = "user_missing"
        await session.commit()
        return {"status": run.status, "run_id": str(run_id)}

    try:
        adapter = build_adapter(run.adapter)
    except Exception as exc:  # noqa: BLE001 - 配置错误要落到 Run 上
        run.status = service.RUN_FAILED
        run.error_message = f"adapter_unavailable: {exc}"[:1000]
        run.completed_at = service._now_naive()
        if task is not None:
            task.status = "failed"
            task.error_message = run.error_message
            task.completed_at = service._now_naive()
        await session.commit()
        return {"status": run.status, "run_id": str(run_id)}

    snapshot = run.config_snapshot or {}
    metrics = list(snapshot.get("metrics") or [])
    judge_metrics = list(snapshot.get("judge_metrics") or [])
    items = await service.select_items(session, run)
    total = len(items)
    started = time.monotonic()
    stopped_reason: str | None = None
    processed = 0

    try:
        for index, item in enumerate(items, start=1):
            if task is not None and await task_control.is_cancelled(session, task.id):
                run.status = service.RUN_CANCELLED
                stopped_reason = service.STOP_CANCELLED
                break
            if (
                settings.RAG_EVAL_SOFT_BUDGET_SECONDS > 0
                and time.monotonic() - started > settings.RAG_EVAL_SOFT_BUDGET_SECONDS
            ):
                stopped_reason = STOP_TIME_BUDGET
                logger.warning(
                    "rag evaluation budget exhausted run={} processed={}/{}",
                    run.id,
                    processed,
                    total,
                )
                break

            await _process_item(
                session,
                run=run,
                item=item,
                adapter=adapter,
                user=user,
                metrics=metrics,
                judge_metrics=judge_metrics,
            )
            processed += 1
            run.last_heartbeat_at = service._now_naive()
            if task is not None:
                task.progress = min(95, 5 + int(processed / total * 90)) if total else 5
                task.current_step = f"evaluated {processed}/{total}"
            await session.commit()
    finally:
        await adapter.aclose()

    await service.finalize_run(session, run, stopped_reason=stopped_reason)

    if task is not None:
        if run.status == service.RUN_CANCELLED:
            task.status = "cancelled"
        elif run.status == service.RUN_FAILED:
            task.status = "failed"
            task.error_message = run.error_message
        else:
            task.status = "completed"
        task.progress = 100
        task.current_step = run.status
        task.completed_at = service._now_naive()
        task.result = {
            "run_id": str(run.id),
            "status": run.status,
            "total_items": run.total_items,
            "failed_items": run.failed_items,
            "unprocessed_items": max(0, run.total_items - processed),
        }
    await session.commit()

    return {
        "status": run.status,
        "run_id": str(run.id),
        "processed": processed,
        "total": total,
        "stopped_reason": stopped_reason,
    }


async def run_rag_evaluation(run_id: str) -> dict[str, Any]:
    """Celery 入口：获取 Run 级 advisory lock 后执行。"""
    rid = uuid.UUID(run_id)
    lock = AdvisoryLock.for_run(rid)
    if not await lock.acquire():
        logger.info("rag evaluation already locked run={}", rid)
        return {"status": "locked", "run_id": run_id}
    try:
        async with SessionLocal() as session:
            return await execute_run(session, rid)
    finally:
        await lock.release()


__all__ = ["execute_run", "run_rag_evaluation"]
