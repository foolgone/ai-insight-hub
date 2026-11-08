"""数据源类型字典表（按用户隔离，多租户）。

- 每行归属一个用户（``owner_user_id``），用户之间互不可见、互不影响；
- ``code`` 是稳定标识，落库在 ``data_sources.type``（字符串），同一用户内唯一，创建后不可修改；
- ``label`` 是展示名，可随时改名，不影响历史数据；
- ``is_system`` 表示「首次访问时播种的默认类型」：可改名/停用，不可删除；
- ``is_active=false`` 表示停用：不再出现在新建下拉，历史数据保持原样。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
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
    """数据源类型（按用户隔离的字典）。"""

    __tablename__ = "datasource_types"
    __table_args__ = (
        # 与 API 层校验保持一致：小写字母开头，允许数字与下划线
        CheckConstraint("code ~ '^[a-z][a-z0-9_]{1,49}$'", name="code_format"),
        Index("uk_datasource_types_owner_code", "owner_user_id", "code", unique=True),
        Index("idx_datasource_types_owner_sort", "owner_user_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # 租户维度：每个用户一套类型（迁移 015 起）
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
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
