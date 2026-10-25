"""Prompt 版本管理三表（数据库设计 §3.12）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

_EMPTY_JSON = text("'{}'::jsonb")


class PromptVersion(Base):
    """Prompt 版本表（数据库为唯一真相源，文件为导出物）。"""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("agent_name", "version", name="agent_version"),
        CheckConstraint(
            "status IN ('draft', 'testing', 'active', 'deprecated')", name="status_valid"
        ),
        Index("idx_prompt_versions_agent", "agent_name", "status"),
        Index(
            "idx_prompt_versions_default",
            "agent_name",
            "is_default",
            postgresql_where=text("is_default = TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'draft'"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    performance_metrics: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, server_default=_EMPTY_JSON
    )
    ab_test_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=_EMPTY_JSON)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime)
    description: Mapped[str | None] = mapped_column(Text)
    changelog: Mapped[str | None] = mapped_column(Text)


class PromptUsageLog(Base):
    """Prompt 使用记录表（按版本使用记录，区别于 llm_calls 的按调用记录）。"""

    __tablename__ = "prompt_usage_logs"
    __table_args__ = (
        CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 100",
            name="quality_score_range",
        ),
        Index("idx_prompt_usage_agent_version", "agent_name", "version", "created_at"),
        Index("idx_prompt_usage_prompt_id", "prompt_version_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prompt_versions.id")
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    datasource_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    duration: Mapped[float | None] = mapped_column(Float)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost: Mapped[float | None] = mapped_column(Float)
    success: Mapped[bool | None] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text)
    quality_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class VersionRollbackLog(Base):
    """Prompt 版本回滚日志表。"""

    __tablename__ = "version_rollback_logs"
    __table_args__ = (
        CheckConstraint("trigger_type IN ('manual', 'auto')", name="trigger_type_valid"),
        CheckConstraint("from_version <> to_version", name="versions_differ"),
        Index("idx_rollback_agent_created", "agent_name", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    from_version: Mapped[str] = mapped_column(String(50), nullable=False)
    to_version: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'manual'")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    error_rate: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
