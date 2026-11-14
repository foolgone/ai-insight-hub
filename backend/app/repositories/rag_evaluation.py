"""``rag_evaluation_runs`` / ``rag_evaluation_results`` 仓储（Phase 3C）。

只负责 SQL；状态机、重试选择、聚合与执行在 service / runner。
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import PaginationParams
from app.models import RagEvaluationResult, RagEvaluationRun
from app.repositories.pagination import paginate
from app.schemas.base import Pagination

SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "created_at": RagEvaluationRun.created_at,
    "completed_at": RagEvaluationRun.completed_at,
}

RESULT_SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "created_at": RagEvaluationResult.created_at,
    "metric_name": RagEvaluationResult.metric_name,
}


# --------------------------------------------------------------------------- Run


async def add_run(session: AsyncSession, run: RagEvaluationRun) -> RagEvaluationRun:
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> RagEvaluationRun | None:
    return await session.get(RagEvaluationRun, run_id)


async def list_runs(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    dataset_id: uuid.UUID | None,
    dataset_version_id: uuid.UUID | None,
    status: str | None,
    execution_mode: str | None,
    adapter: str | None,
    parent_run_id: uuid.UUID | None,
    params: PaginationParams,
) -> tuple[list[RagEvaluationRun], Pagination]:
    stmt: Select = select(RagEvaluationRun)
    if user_id is not None:
        stmt = stmt.where(RagEvaluationRun.user_id == user_id)
    if dataset_id is not None:
        stmt = stmt.where(RagEvaluationRun.dataset_id == dataset_id)
    if dataset_version_id is not None:
        stmt = stmt.where(RagEvaluationRun.dataset_version_id == dataset_version_id)
    if status:
        stmt = stmt.where(RagEvaluationRun.status == status)
    if execution_mode:
        stmt = stmt.where(RagEvaluationRun.execution_mode == execution_mode)
    if adapter:
        stmt = stmt.where(RagEvaluationRun.adapter == adapter)
    if parent_run_id is not None:
        stmt = stmt.where(RagEvaluationRun.parent_run_id == parent_run_id)
    return await paginate(session, stmt, params, sortable=SORTABLE)


async def list_child_runs(
    session: AsyncSession, parent_run_id: uuid.UUID
) -> list[RagEvaluationRun]:
    rows = await session.execute(
        select(RagEvaluationRun).where(RagEvaluationRun.parent_run_id == parent_run_id)
    )
    return list(rows.scalars().all())


async def list_stale_runs(
    session: AsyncSession, *, heartbeat_before: Any
) -> list[RagEvaluationRun]:
    rows = await session.execute(
        select(RagEvaluationRun)
        .where(
            RagEvaluationRun.status == "running",
            RagEvaluationRun.last_heartbeat_at.is_not(None),
            RagEvaluationRun.last_heartbeat_at < heartbeat_before,
        )
        .order_by(RagEvaluationRun.last_heartbeat_at)
    )
    return list(rows.scalars().all())


async def list_runs_for_summary(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    dataset_id: uuid.UUID | None,
    execution_mode: str | None,
    adapter: str | None,
    limit: int = 1000,
) -> list[RagEvaluationRun]:
    """跨 Run 汇总用：只取已结束且已生成 aggregate 的 Run（最新优先）。"""
    stmt = (
        select(RagEvaluationRun)
        .where(RagEvaluationRun.aggregate.is_not(None))
        .order_by(RagEvaluationRun.created_at.desc())
        .limit(limit)
    )
    if user_id is not None:
        stmt = stmt.where(RagEvaluationRun.user_id == user_id)
    if dataset_id is not None:
        stmt = stmt.where(RagEvaluationRun.dataset_id == dataset_id)
    if execution_mode:
        stmt = stmt.where(RagEvaluationRun.execution_mode == execution_mode)
    if adapter:
        stmt = stmt.where(RagEvaluationRun.adapter == adapter)
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


# --------------------------------------------------------------------------- Result


def _result_values(row: RagEvaluationResult) -> dict[str, Any]:
    """批量 INSERT 用的显式列值。

    ``pg_insert`` 会绕过 ORM/服务端默认值，未显式赋值的 NOT NULL 列必须在这里兜底，
    否则会撞 ``null value in column ... violates not-null constraint``。
    """
    return {
        "run_id": row.run_id,
        "dataset_item_id": row.dataset_item_id,
        "trace_id": row.trace_id,
        "metric_name": row.metric_name,
        "metric_version": row.metric_version or "v1",
        "status": row.status,
        "score": row.score,
        "skipped_reason": row.skipped_reason,
        "details": row.details or {},
        "judge_config": row.judge_config or {},
        "raw_output": row.raw_output,
        "raw_truncated": bool(row.raw_truncated),
        "latency_ms": row.latency_ms,
        "error_message": row.error_message,
    }


async def add_results_ignore_conflicts(
    session: AsyncSession, rows: Sequence[RagEvaluationResult]
) -> int:
    """批量写入；同一 (run,item,metric,version) 已存在则跳过（幂等/重投递安全）。"""
    if not rows:
        return 0
    stmt = pg_insert(RagEvaluationResult).values([_result_values(row) for row in rows])
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["run_id", "dataset_item_id", "metric_name", "metric_version"]
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def list_results(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    metric_name: str | None,
    status: str | None,
    dataset_item_id: uuid.UUID | None,
    params: PaginationParams,
) -> tuple[list[RagEvaluationResult], Pagination]:
    stmt: Select = select(RagEvaluationResult).where(RagEvaluationResult.run_id == run_id)
    if metric_name:
        stmt = stmt.where(RagEvaluationResult.metric_name == metric_name)
    if status:
        stmt = stmt.where(RagEvaluationResult.status == status)
    if dataset_item_id is not None:
        stmt = stmt.where(RagEvaluationResult.dataset_item_id == dataset_item_id)
    return await paginate(session, stmt, params, sortable=RESULT_SORTABLE)


async def results_for_run(session: AsyncSession, run_id: uuid.UUID) -> list[RagEvaluationResult]:
    rows = await session.execute(
        select(RagEvaluationResult)
        .where(RagEvaluationResult.run_id == run_id)
        .order_by(RagEvaluationResult.dataset_item_id, RagEvaluationResult.metric_name)
    )
    return list(rows.scalars().all())


async def results_for_item(
    session: AsyncSession, *, run_id: uuid.UUID, dataset_item_id: uuid.UUID
) -> list[RagEvaluationResult]:
    rows = await session.execute(
        select(RagEvaluationResult).where(
            RagEvaluationResult.run_id == run_id,
            RagEvaluationResult.dataset_item_id == dataset_item_id,
        )
    )
    return list(rows.scalars().all())


__all__ = [
    "RESULT_SORTABLE",
    "SORTABLE",
    "add_results_ignore_conflicts",
    "add_run",
    "get_run",
    "list_child_runs",
    "list_results",
    "list_runs",
    "list_runs_for_summary",
    "list_stale_runs",
    "results_for_item",
    "results_for_run",
]
