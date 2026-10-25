"""分页 / 过滤 / 排序依赖（API 设计 §3.2、§3.3）。

- 查询参数：``page``（从 1）/ ``limit``（默认 20，上限 100）/ ``sort``（``-`` 前缀为降序）；
- 排序字段必须显式白名单（``sortable``），防止任意列排序导致的信息泄露；
- 响应分页对象见 ``app.schemas.base.Page``。
"""
from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.schemas.base import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Pagination


class PaginationParams:
    """分页查询参数依赖（也可直接实例化用于 service 层测试）。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码（从 1 开始）")] = 1,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=MAX_PAGE_SIZE,
                description="每页条数（默认 20，最大 100）",
            ),
        ] = DEFAULT_PAGE_SIZE,
        sort: Annotated[
            str | None,
            Query(description="排序字段，前缀 - 表示降序（如 -created_at）"),
        ] = None,
    ) -> None:
        self.page = page
        self.limit = limit
        self.sort = sort

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


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


__all__ = ["PaginationParams", "apply_sort", "paginate"]
