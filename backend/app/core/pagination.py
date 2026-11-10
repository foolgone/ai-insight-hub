"""分页查询参数（HTTP 无关）。

- ``page``（从 1）/ ``limit``（默认 20，上限 100）/ ``sort``（``-`` 前缀为降序）；
- 排序字段必须显式白名单（``sortable``），防止任意列排序导致的信息泄露；
- 响应分页对象见 ``app.schemas.base.Pagination``。

**HTTP 解析在 ``app/api/deps.py::pagination_params``**（带 ``Query`` 约束），
分页执行在 ``app.repositories.pagination``。这样 ``core`` 不再依赖 FastAPI，
仓储层也不会被 Web 框架传染。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.base import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class PaginationParams:
    """分页查询参数（可直接实例化，用于 service / 仓储层测试）。"""

    page: int = 1
    limit: int = DEFAULT_PAGE_SIZE
    sort: str | None = None

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


__all__ = ["PaginationParams"]
