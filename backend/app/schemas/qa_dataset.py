"""RAG 评测数据集 Schemas（Phase 1）。

约定（沿用 ``BaseSchema``）：
- 入参兼容 camelCase，内部 snake_case；
- 响应路由统一 ``response_model_by_alias=False``（输出 snake_case）；
- 导入接口的 ``items`` 保持 ``dict``：逐条校验、**收集全部错误**后再决定是否写入，
  避免 Pydantic 在第一条就抛 422、拿不到行号。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema

DatasetSourceType = Literal["doc", "conv", "mixed"]
ItemSplit = Literal["train", "valid", "test"]

MAX_IMPORT_ITEMS = 2000


class GoldEvidence(BaseSchema):
    """标准证据（快照）。

    ``evidence_text`` 必填：只存 document_id 时，原始文档更新后无法复现历史评测。
    """

    document_id: str | None = Field(default=None, max_length=200)
    chunk_id: str | None = Field(default=None, max_length=200)
    evidence_text: str = Field(min_length=10, max_length=5000)
    page_number: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("document_id", "chunk_id")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("evidence_text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class QaDatasetCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source_type: DatasetSourceType = "mixed"


class QaDatasetUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source_type: DatasetSourceType | None = None


class QaDatasetItemCreate(BaseSchema):
    item_key: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1, max_length=10000)
    gold_answer: str | None = Field(default=None, max_length=20000)
    gold_evidence: list[GoldEvidence] = Field(default_factory=list, max_length=50)
    category: str | None = Field(default=None, max_length=100)
    difficulty: str | None = Field(default=None, max_length=20)
    source: str | None = Field(default=None, max_length=50)
    split: ItemSplit = "test"
    metadata: dict[str, Any] = Field(default_factory=dict)


class QaDatasetItemUpdate(BaseSchema):
    """草稿版本的条目更新（发布后由 service 拒绝）。"""

    query: str | None = Field(default=None, min_length=1, max_length=10000)
    gold_answer: str | None = Field(default=None, max_length=20000)
    gold_evidence: list[GoldEvidence] | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, max_length=100)
    difficulty: str | None = Field(default=None, max_length=20)
    source: str | None = Field(default=None, max_length=50)
    split: ItemSplit | None = None
    metadata: dict[str, Any] | None = None


class QaDatasetItemRead(BaseSchema):
    id: uuid.UUID
    item_key: str
    query: str
    gold_answer: str | None
    gold_evidence: list[dict[str, Any]]
    category: str | None
    difficulty: str | None
    source: str | None
    split: str
    metadata: dict[str, Any]
    created_at: datetime


class QaDatasetVersionRead(BaseSchema):
    id: uuid.UUID
    dataset_id: uuid.UUID
    version: int
    status: str
    item_count: int
    checksum: str | None
    note: str | None
    published_at: datetime | None
    created_at: datetime


class QaDatasetRead(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None
    source_type: str
    created_at: datetime
    updated_at: datetime


class QaDatasetDetail(QaDatasetRead):
    versions: list[QaDatasetVersionRead] = Field(default_factory=list)


class QaDatasetVersionCreate(BaseSchema):
    note: str | None = Field(default=None, max_length=2000)
    # 从已有版本复制条目（copy-on-write），不传则空版本
    from_version_id: uuid.UUID | None = None


class QaDatasetImportRequest(BaseSchema):
    """导入条目。

    ``items`` 保持原始 dict：逐条校验并汇总错误（带 1-based 行号），
    有任何错误则整批不写入。
    """

    items: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_IMPORT_ITEMS)


class QaDatasetImportError(BaseSchema):
    index: int = Field(ge=1, description="1-based 行号（对应请求 items 的下标 +1）")
    field: str
    message: str


class QaDatasetImportResult(BaseSchema):
    imported: int
    version_item_count: int


class QaDatasetImportFailure(BaseSchema):
    """导入失败详情（放在 error.details 里）。"""

    errors: list[QaDatasetImportError]
    error_count: int


class SplitCounts(BaseSchema):
    train: int = 0
    valid: int = 0
    test: int = 0


class EvidenceCoverage(BaseSchema):
    with_evidence: int
    without_evidence: int
    coverage_rate: float


class QaDatasetStats(BaseSchema):
    dataset_id: uuid.UUID
    version_id: uuid.UUID
    item_count: int
    split_counts: SplitCounts
    category_counts: dict[str, int]
    evidence: EvidenceCoverage
