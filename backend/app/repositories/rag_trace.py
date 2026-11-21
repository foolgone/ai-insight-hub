"""``rag_traces`` 仓储（Phase 2）。

只负责 SQL；执行编排在 ``app.services.rag.execute``，指标在 Phase 3。
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import PaginationParams
from app.models import RagTrace
from app.repositories.pagination import paginate
from app.schemas.base import Pagination

SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "created_at": RagTrace.created_at,
    "latency_ms": RagTrace.latency_ms,
}


async def add_trace(session: AsyncSession, trace: RagTrace) -> RagTrace:
    session.add(trace)
    await session.flush()
    await session.refresh(trace)
    return trace


async def get_trace(session: AsyncSession, trace_id: uuid.UUID) -> RagTrace | None:
    return await session.get(RagTrace, trace_id)


async def get_by_idempotency_key(session: AsyncSession, idempotency_key: str) -> RagTrace | None:
    return await session.scalar(select(RagTrace).where(RagTrace.idempotency_key == idempotency_key))


async def list_traces(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    dataset_item_id: uuid.UUID | None,
    status: str | None,
    adapter: str | None,
    params: PaginationParams,
) -> tuple[list[RagTrace], Pagination]:
    stmt: Select = select(RagTrace)
    if user_id is not None:
        stmt = stmt.where(RagTrace.user_id == user_id)
    if task_id is not None:
        stmt = stmt.where(RagTrace.task_id == task_id)
    if dataset_item_id is not None:
        stmt = stmt.where(RagTrace.dataset_item_id == dataset_item_id)
    if status:
        stmt = stmt.where(RagTrace.status == status)
    if adapter:
        stmt = stmt.where(RagTrace.adapter == adapter)
    return await paginate(session, stmt, params, sortable=SORTABLE)


__all__ = [
    "SORTABLE",
    "add_trace",
    "get_by_idempotency_key",
    "get_trace",
    "list_traces",
]
