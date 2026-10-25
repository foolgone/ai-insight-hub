"""分析结果与知识库两表（数据库设计 §3.5 ~ §3.6）。

说明：``analysis_results.data_id`` 为逻辑外键（不建 REFERENCES）；
知识库的中文表达式 GIN(pg_trgm) 索引在迁移 002 中以 ``op.execute`` 创建。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

EMBEDDING_DIM = 384
_FALSE = text("false")
_ONE = text("1")


class AnalysisResult(Base):
    """分析结果表（质量评估 / 知识提取 / 洞察分析共用）。"""

    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint(
            "analysis_type IN ('quality', 'knowledge', 'insight', 'other')",
            name="analysis_type_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        Index("idx_analysis_datasource_id", "datasource_id", "created_at"),
        Index("idx_analysis_data_id", "data_id"),
        Index("idx_analysis_type", "analysis_type"),
        Index("idx_analysis_created_at", "created_at"),
        Index("idx_analysis_result", "result", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    datasource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 逻辑外键 -> cleaned_data(id)
    data_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_version: Mapped[str | None] = mapped_column(String(50))
    ai_model: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    processing_duration: Mapped[float | None] = mapped_column(Float)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class KnowledgeBase(Base):
    """知识库（FAQ）表。"""

    __tablename__ = "knowledge_base"
    __table_args__ = (
        CheckConstraint("source IN ('seed', 'manual', 'extracted')", name="source_valid"),
        CheckConstraint("status IN ('active', 'archived', 'needs_review')", name="status_valid"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 100", name="quality_score_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        Index("idx_kb_datasource_id", "datasource_id"),
        Index("idx_kb_category", "category"),
        Index("idx_kb_frequency", "frequency"),
        Index("idx_kb_status", "status"),
        Index("idx_kb_is_seed", "datasource_id", "is_seed"),
        Index("idx_kb_source", "datasource_id", "source"),
        Index(
            "idx_kb_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    datasource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    frequency: Mapped[int | None] = mapped_column(Integer, server_default=_ONE)
    quality_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_dialogue_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True))
    )
    variations: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'extracted'")
    )
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=_FALSE)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
