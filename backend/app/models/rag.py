"""RAG 执行链路 ORM（Phase 2）。

- ``rag_traces``：一次 RAG 调用的完整快照（问题、上下文、答案、配置、耗时、错误）。

不变量：
- ``context_source`` 必须如实反映上下文的来源（``hybrid_search`` / ``agent_chat`` / ``none``），
  Phase 3 的 Faithfulness 只接受 ``agent_chat``；
- 外部未提供的字段（score / token_usage）留空并记入 ``missing``，不补零。

> ``rag_eval_results`` 推迟到 Phase 3 与指标写入方一起建表（避免空表）。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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

_EMPTY_ARRAY = text("'[]'::jsonb")
_EMPTY_OBJECT = text("'{}'::jsonb")


class RagTrace(Base):
    """一次 RAG 查询（retrieve 或 query）的执行快照。"""

    __tablename__ = "rag_traces"
    __table_args__ = (
        CheckConstraint("mode IN ('retrieve', 'query')", name="rag_trace_mode_valid"),
        CheckConstraint("status IN ('success', 'failed')", name="rag_trace_status_valid"),
        CheckConstraint(
            "context_source IN ('hybrid_search', 'agent_chat', 'none')",
            name="rag_trace_context_source_valid",
        ),
        # 评测批次幂等：Phase 3 会写 task:{task_id}:item:{item_id}；临时查询为 NULL（PG 允许多个 NULL）
        Index("uk_rag_traces_idempotency_key", "idempotency_key", unique=True),
        Index("idx_rag_traces_user_created", "user_id", "created_at"),
        Index("idx_rag_traces_task_status", "task_id", "status"),
        Index("idx_rag_traces_dataset_item", "dataset_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("qa_dataset_items.id", ondelete="SET NULL"),
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    adapter: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    context_source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'none'")
    )
    external_session_id: Mapped[str | None] = mapped_column(String(100))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    # [{document_id, chunk_id, title, content, score, rank, metadata, truncated}]
    retrieved_contexts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_ARRAY
    )
    raw_response: Mapped[Any | None] = mapped_column(JSONB)
    model_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    retrieval_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    prompt_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # 外部未提供的字段名（如 token_usage / score），用于区分「缺失」与「0」
    missing: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=_EMPTY_ARRAY)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


__all__ = ["RagTrace"]
