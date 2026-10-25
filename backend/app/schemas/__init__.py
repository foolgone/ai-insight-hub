"""Pydantic Schemas 包。

- 基类与通用结构见 ``app.schemas.base``；
- 响应字段必须 snake_case：路由需显式 ``response_model_by_alias=False``
  （见 docs/04-development/05-API命名规范.md）。
"""
from app.schemas.base import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    ORMSchema,
    Page,
    Pagination,
)

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
