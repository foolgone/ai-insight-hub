"""RAG 评测数据集 ORM（Phase 1：数据集 / 版本 / 条目）。

设计要点（见 ``docs/repair/01-implementation-plan.md``）：
- 数据集与版本分离：**发布后的版本不可变**，修改一律产生新版本；
- 条目保存 ``gold_evidence`` 快照（含 ``evidence_text``），不依赖外部文档当前状态；
- 与现有「对话质量评估」链路完全隔离（不复用 ``analysis_results``）。

版本不可变由 service 层保证（发布后拒绝写操作），DB 仅提供状态约束。
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

_EMPTY_JSON = text("'[]'::jsonb")
_EMPTY_OBJECT = text("'{}'::jsonb")


class QaDataset(Base):
    """评测数据集（一组可版本化的 RAG 评测样本）。"""

    __tablename__ = "qa_datasets"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('doc', 'conv', 'mixed')", name="qa_dataset_source_type_valid"
        ),
        Index("uk_qa_datasets_user_name", "user_id", "name", unique=True),
        Index("idx_qa_datasets_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # doc=文档类 Gold；conv=真实客服对话类 Gold；mixed=混合（仅用于自定义数据集）
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'mixed'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QaDatasetVersion(Base):
    """数据集版本。

    ``status``：draft（可改）→ published（不可变）→ archived（历史保留）。
    发布时写入 ``checksum`` 与 ``item_count``，用于判断条目是否被篡改。
    """

    __tablename__ = "qa_dataset_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="qa_dataset_version_status_valid",
        ),
        Index("uk_qa_dataset_versions_dataset_version", "dataset_id", "version", unique=True),
        Index("idx_qa_dataset_versions_dataset_status", "dataset_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("qa_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # 发布时计算：条目内容规范化 JSON 的 sha256（范围见 qa_dataset_service.compute_checksum）
    checksum: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class QaDatasetItem(Base):
    """评测样本（一个问题 + 标准答案 + 标准证据快照）。"""

    __tablename__ = "qa_dataset_items"
    __table_args__ = (
        CheckConstraint(
            "split IN ('train', 'valid', 'test')",
            name="qa_dataset_item_split_valid",
        ),
        Index("uk_qa_dataset_items_version_key", "version_id", "item_key", unique=True),
        Index("idx_qa_dataset_items_version_split", "version_id", "split"),
        Index("idx_qa_dataset_items_version_category", "version_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("qa_dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 稳定外部键（如 CONV-10215 / Q001），版本内唯一
    item_key: Mapped[str] = mapped_column(String(80), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    gold_answer: Mapped[str | None] = mapped_column(Text)
    # [{document_id, chunk_id, evidence_text, page_number, metadata}]
    gold_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=_EMPTY_JSON
    )
    category: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(50))
    split: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'test'"))
    # 原始字段快照（session_id、llm 预筛分等）；列名保持 metadata，属性避开 SQLAlchemy 保留名
    item_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=_EMPTY_OBJECT
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


__all__ = ["QaDataset", "QaDatasetItem", "QaDatasetVersion"]
