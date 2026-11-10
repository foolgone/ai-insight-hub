"""分页查询执行（持久化中立：不依赖 FastAPI，只依赖 SQLAlchemy 与 DTO）。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import PaginationParams
from app.schemas.base import Pagination


def apply_sort(
    stmt: Select,
    sort: str | None,
    sortable: Mapping[str, InstrumentedAttribute] | None,
) -> Select:
    """按白名单应用排序；未知字段忽略（不抛错，避免暴露列名）。"""
    if not sort or not sortable:
        return stmt
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    column = sortable.get(field)
    if column is None:
        return stmt
    return stmt.order_by(column.desc() if descending else column.asc())


async def paginate(
    session: AsyncSession,
    stmt: Select,
    params: PaginationParams,
    *,
    sortable: Mapping[str, InstrumentedAttribute] | None = None,
) -> tuple[list[Any], Pagination]:
    """执行分页查询，返回 ``(items, pagination)``。"""
    ordered = apply_sort(stmt, params.sort, sortable)
    count_stmt = select(func.count()).select_from(ordered.order_by(None).subquery())
    total = int(await session.scalar(count_stmt) or 0)
    rows = list(
        (await session.execute(ordered.offset(params.offset).limit(params.limit))).scalars().all()
    )
    return rows, Pagination.build(page=params.page, limit=params.limit, total=total)


__all__ = ["apply_sort", "paginate"]
