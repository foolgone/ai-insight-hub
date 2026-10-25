"""API Key / 审计日志 / Webhook 三表（数据库设计 §3.9 ~ §3.11）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

_SCOPES_DEFAULT = text("ARRAY['read']::text[]")
_WEBHOOK_EVENTS_DEFAULT = text("ARRAY['task.completed', 'task.failed']::text[]")
_RATE_LIMIT_DEFAULT = text(
    """'{"requests_per_minute": 60, "requests_per_hour": 1000, """
    """"requests_per_day": 10000}'::jsonb"""
)


class ApiKey(Base):
    """API 密钥表（表先落库，接口 Phase 2）。"""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_apikeys_user_id", "user_id"),
        Index("idx_apikeys_key_hash", "key_hash"),
        Index("idx_apikeys_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), server_default=_SCOPES_DEFAULT)
    rate_limit: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, server_default=_RATE_LIMIT_DEFAULT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    usage_count: Mapped[int | None] = mapped_column(BigInteger, server_default=text("0"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    ip_whitelist: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class AuditLog(Base):
    """审计日志表（MVP 普通表，不分区；主键 BIGSERIAL）。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_user_id", "user_id", "created_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_action", "action", "created_at"),
        Index("idx_audit_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class Webhook(Base):
    """Webhook 配置表（表先落库，接口 Phase 2）。"""

    __tablename__ = "webhooks"
    __table_args__ = (
        Index("idx_webhooks_user_id", "user_id"),
        Index("idx_webhooks_is_active", "is_active"),
        Index("idx_webhooks_events", "events", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=_WEBHOOK_EVENTS_DEFAULT
    )
    secret: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime)
    failure_count: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
