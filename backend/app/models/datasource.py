"""数据源与数据管道三表（数据库设计 §3.2 ~ §3.4）。

说明：
- ``cleaned_data.raw_data_id`` 是**逻辑外键**（不建 REFERENCES），由应用层保证一致性；
- 中文检索的表达式 GIN(pg_trgm) 索引无法用 SQLAlchemy ``Index`` 表达，统一在
  Alembic 迁移 ``002`` 中以 ``op.execute`` 创建；
- 时间倒序索引在 ORM 中按普通列声明，迁移中按设计补 ``DESC``。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
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

_CONFIG_DEFAULT = text(
    """'{"auto_clean": true, "auto_evaluate": true, """
    """"evaluation_dimensions": ["accuracy", "completeness", "tone", """
    """"compliance", "hallucination"], "notification_email": "user@example.com"}'::jsonb"""
)
_STATISTICS_DEFAULT = text(
    """'{"total_records": 0, "cleaned_records": 0, "quality_score_avg": 0, """
    """"last_processed_at": null}'::jsonb"""
)
_METADATA_DEFAULT = text("'{}'::jsonb")


class DataSource(Base):
    """数据源表。"""

    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint(
            "type IN ('customer_service', 'sales', 'support', 'other')", name="type_valid"
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'processing', 'error')", name="status_valid"
        ),
        CheckConstraint(
            "workflow_status IN ('created', 'data_uploaded', 'data_cleaned', "
            "'knowledge_built', 'ready')",
            name="workflow_status_valid",
        ),
        Index(
            "idx_datasources_user_id",
            "user_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_datasources_status",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_datasources_type", "type", postgresql_where=text("deleted_at IS NULL")),
        Index(
            "idx_datasources_user_status",
            "user_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_datasources_created_at", "created_at"),
        Index("idx_datasources_config", "config", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default=_CONFIG_DEFAULT)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'active'"))
    workflow_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'created'")
    )
    statistics: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, server_default=_STATISTICS_DEFAULT
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class RawData(Base):
    """原始数据表（MVP 普通表，不分区）。"""

    __tablename__ = "raw_data"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')", name="status_valid"
        ),
        Index("idx_raw_data_datasource_id", "datasource_id", "created_at"),
        Index("idx_raw_data_status", "status"),
        Index("idx_raw_data_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    datasource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    file_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'pending'")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class CleanedData(Base):
    """清洗后数据表（MVP 普通表，不分区）。"""

    __tablename__ = "cleaned_data"
    __table_args__ = (
        CheckConstraint("quality_score >= 0 AND quality_score <= 100", name="quality_score_range"),
        Index("idx_cleaned_data_datasource_id", "datasource_id", "created_at"),
        Index("idx_cleaned_data_dialogue_id", "dialogue_id"),
        Index("idx_cleaned_data_timestamp", "timestamp"),
        Index("idx_cleaned_data_quality_score", "quality_score"),
        Index("idx_cleaned_data_raw_data_id", "raw_data_id"),
        Index(
            "idx_cleaned_data_ds_quality",
            "datasource_id",
            "quality_score",
            postgresql_where=text("quality_score < 70"),
        ),
        Index(
            "idx_cleaned_data_embedding",
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
    # 逻辑外键 -> raw_data(id)：不建 REFERENCES（理由见数据库设计 §3.4）
    raw_data_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dialogue_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    ai_response: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, server_default=_METADATA_DEFAULT
    )
    quality_score: Mapped[float | None] = mapped_column(Float)
    issues: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    agent_version: Mapped[str | None] = mapped_column(String(50))
    processing_duration: Mapped[float | None] = mapped_column(Float)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
