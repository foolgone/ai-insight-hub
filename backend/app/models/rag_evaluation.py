"""RAG 评测 Run / Result ORM（Phase 3C）。

- ``rag_evaluation_runs``：一次固定配置的批量评测（含配置快照、计数、心跳、聚合）；
- ``rag_evaluation_results``：Run × 条目 × 指标 的结果。

唯一键 ``(run_id, dataset_item_id, metric_name, metric_version)`` 成立的前提：
**Run 内 Judge 配置固定**（模型 / Prompt / 指标版本），换配置必须新建 Run。
"""
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

_EMPTY_OBJECT = text("'{}'::jsonb")


class RagEvaluationRun(Base):
    """一次批量评测执行。"""

    __tablename__ = "rag_evaluation_runs"
    __table_args__ = (
        CheckConstraint("retry_scope IN ('all', 'failed_only')", name="retry_scope_valid"),
        CheckConstraint("execution_mode IN ('retrieve', 'query')", name="mode_valid"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial_failed', "
            "'failed', 'cancelled')",
            name="status_valid",
        ),
        Index("uk_rag_evaluation_runs_task_id", "task_id", unique=True),
        Index("idx_rag_evaluation_runs_user_created", "user_id", "created_at"),
        Index("idx_rag_evaluation_runs_dataset_version", "dataset_version_id"),
        Index("idx_rag_evaluation_runs_status", "status"),
        Index("idx_rag_evaluation_runs_parent", "parent_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_evaluation_runs.id", ondelete="SET NULL"),
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    retry_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'all'")
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("qa_datasets.id", ondelete="SET NULL"),
    )
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("qa_dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dataset_checksum: Mapped[str | None] = mapped_column(String(64))
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    adapter: Mapped[str] = mapped_column(String(50), nullable=False)
    retrieval_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    judge_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    # {"mode": "all|failed_only", "item_ids": [...]}
    item_selection: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    skipped_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    aggregate: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class RagEvaluationResult(Base):
    """一条样本的一个指标结果。"""

    __tablename__ = "rag_evaluation_results"
    __table_args__ = (
        CheckConstraint("status IN ('evaluated', 'skipped', 'failed')", name="status_valid"),
        Index(
            "uk_rag_evaluation_results_run_item_metric",
            "run_id",
            "dataset_item_id",
            "metric_name",
            "metric_version",
            unique=True,
        ),
        Index("idx_rag_evaluation_results_run_metric", "run_id", "metric_name", "status"),
        Index("idx_rag_evaluation_results_run_status", "run_id", "status"),
        Index("idx_rag_evaluation_results_trace", "trace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("qa_dataset_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rag_traces.id", ondelete="SET NULL"),
    )
    metric_name: Mapped[str] = mapped_column(String(40), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    skipped_reason: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    judge_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    raw_output: Mapped[str | None] = mapped_column(Text)
    raw_truncated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


__all__ = ["RagEvaluationResult", "RagEvaluationRun"]
