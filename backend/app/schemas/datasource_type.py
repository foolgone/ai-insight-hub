"""数据源类型 Schemas（字典表 CRUD）。

- ``code`` 创建后不可改（``data_sources.type`` 直接存它，改了会让历史数据失联）；
- 列表项额外带 ``usage_count``，前端据此禁用「删除」。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, ORMSchema


class DataSourceTypeCreate(BaseSchema):
    label: str = Field(min_length=1, max_length=50)
    # 可选：留空则自动生成 t_xxxxxxxx；自定义时须为小写字母开头
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None


class DataSourceTypeUpdate(BaseSchema):
    label: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None
    is_active: bool | None = None


class DataSourceTypeItem(ORMSchema):
    id: uuid.UUID
    code: str
    label: str
    description: str | None = None
    sort_order: int = 0
    is_system: bool = False
    is_active: bool = True
    usage_count: int = 0
    created_at: datetime | None = None


class DataSourceTypeList(BaseSchema):
    items: list[DataSourceTypeItem]


__all__ = [
    "DataSourceTypeCreate",
    "DataSourceTypeItem",
    "DataSourceTypeList",
    "DataSourceTypeUpdate",
]
