"""reports 表（数据库设计 §3.7）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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


class Report(Base):
    """报告表。"""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('quality', 'knowledge', 'insight', 'comprehensive')",
            name="report_type_valid",
        ),
        CheckConstraint("format IN ('pdf', 'excel', 'markdown', 'html')", name="format_valid"),
        CheckConstraint("status IN ('generating', 'completed', 'failed')", name="status_valid"),
        Index("idx_reports_datasource_id", "datasource_id", "created_at"),
        Index("idx_reports_user_id", "user_id", "created_at"),
        Index("idx_reports_status", "status"),
        Index("idx_reports_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    datasource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_url: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'generating'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    generation_duration: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    view_count: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    download_count: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
