"""llm_calls 表（数据库设计 §3.13）。

每次 LLM 调用落一行，成本/用量/失败排查的唯一数据源；
幂等键 ``f"{task_id}:{attempt}"`` 由 UNIQUE 索引保证。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class LlmCall(Base):
    """LLM 调用记录表。"""

    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed')", name="status_valid"),
        Index("uk_llm_calls_idempotency", "idempotency_key", unique=True),
        Index("idx_llm_calls_user_date", "user_id", "created_at"),
        Index("idx_llm_calls_datasource_date", "datasource_id", "created_at"),
        Index("idx_llm_calls_service_model", "service", "model", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    datasource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        # 数据源物理删除时保留成本记录（SET NULL），避免 force 删除被外键阻塞
        ForeignKey("data_sources.id", ondelete="SET NULL"),
    )
    # 逻辑关联 tasks.id（不建外键，任务可能被清理）
    task_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(100))
    agent_version: Mapped[str | None] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    input_cost: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    output_cost: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    duration: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'success'")
    )
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
