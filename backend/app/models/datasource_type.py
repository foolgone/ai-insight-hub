"""数据源类型字典表（可配置的「类型」）。

- ``code`` 是稳定标识，落库在 ``data_sources.type``（字符串），创建后不可修改；
- ``label`` 是展示名，可随时改名，不影响历史数据；
- ``is_system`` 内置类型（客服对话/销售/支持/其他）不可删除；
- ``is_active=false`` 表示停用：不再出现在新建下拉，历史数据保持原样。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class DataSourceType(Base):
    """数据源类型（全局字典，非按用户隔离）。"""

    __tablename__ = "datasource_types"
    __table_args__ = (
        # 与 API 层校验保持一致：小写字母开头，允许数字与下划线
        CheckConstraint("code ~ '^[a-z][a-z0-9_]{1,49}$'", name="code_format"),
        Index("uk_datasource_types_code", "code", unique=True),
        Index("idx_datasource_types_sort", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
