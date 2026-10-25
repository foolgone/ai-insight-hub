"""tasks 表（数据库设计 §3.8）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Task(Base):
    """任务队列表（5 态状态机：pending/running/completed/failed/cancelled）。"""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('clean', 'evaluate', 'extract', 'analyze', 'report')",
            name="task_type_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        Index("idx_tasks_datasource_id", "datasource_id", "created_at"),
        Index("idx_tasks_user_id", "user_id", "created_at"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_task_type", "task_type"),
        Index("idx_tasks_celery_task_id", "celery_task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_name: Mapped[str | None] = mapped_column(String(255))
    datasource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'pending'")
    )
    progress: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    current_step: Mapped[str | None] = mapped_column(String(255))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration: Mapped[float | None] = mapped_column(Float)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    max_retries: Mapped[int | None] = mapped_column(Integer, server_default=text("3"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
