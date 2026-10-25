"""users 表（数据库设计 §3.1）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

_QUOTA_DEFAULT = text(
    """'{"max_datasources": 10, "max_monthly_records": 100000, """
    """"max_monthly_tokens": 1000000}'::jsonb"""
)
_USAGE_DEFAULT = text(
    """'{"datasources_count": 0, "monthly_records": 0, "monthly_tokens": 0}'::jsonb"""
)


class User(Base):
    """用户表。"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user', 'viewer')", name="role_valid"),
        Index("idx_users_email", "email", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_users_role", "role", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_users_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'user'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    quota: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=_QUOTA_DEFAULT)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=_USAGE_DEFAULT)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
