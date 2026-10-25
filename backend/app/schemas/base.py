"""Schema 基类（API 命名规范 / API 设计 §3.2、§3.4）。

约定：
- **入参**：兼容 camelCase（``alias_generator=to_camel`` + ``populate_by_name=True``），
  内部属性始终 snake_case；
- **响应**：必须输出 snake_case —— 路由需显式传 ``response_model_by_alias=False``
  （否则 Pydantic 会用 camelCase 别名序列化）；
- **分页**：``{items, pagination:{page, limit, total, pages, has_next, has_prev}}``，
  默认 20 / 上限 100（API §3.2）；
- **错误**：``{"error": {"code", "message", "details"?}}``（API §3.4）。
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

T = TypeVar("T")


class BaseSchema(BaseModel):
    """请求/响应 Schema 基类（camelCase 入参兼容）。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ORMSchema(BaseSchema):
    """可从 ORM 实体直接构造的响应 Schema。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        str_strip_whitespace=True,
    )


class Pagination(BaseModel):
    """分页元信息。"""

    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool

    @classmethod
    def build(cls, *, page: int, limit: int, total: int) -> Pagination:
        """按总数与页大小计算分页元信息。"""
        if limit <= 0:
            raise ValueError("limit must be positive")
        pages = (total + limit - 1) // limit
        return cls(
            page=page,
            limit=limit,
            total=total,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class Page(BaseModel, Generic[T]):
    """分页响应包装：``{items, pagination}``。"""

    items: list[T]
    pagination: Pagination


class ErrorDetail(BaseModel):
    """错误详情。"""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """统一错误响应体。"""

    error: ErrorDetail


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "ORMSchema",
    "Page",
    "Pagination",
]
