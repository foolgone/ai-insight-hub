"""知识库 Schemas（API 设计 §8）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema, ORMSchema


class FAQItem(ORMSchema):
    id: uuid.UUID
    question: str
    answer: str
    category: str | None = None
    frequency: int | None = None
    confidence: float | None = None
    quality_score: float | None = None
    variations: list[str] | None = None
    tags: list[str] | None = None
    status: str
    source: str
    is_seed: bool
    created_at: datetime | None = None


class FAQCreate(BaseSchema):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    variations: list[str] | None = None


class FAQUpdate(BaseSchema):
    question: str | None = Field(default=None, min_length=1, max_length=2000)
    answer: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    variations: list[str] | None = None
    status: Literal["active", "archived", "needs_review"] | None = None


class KnowledgeExtractionRequest(BaseSchema):
    min_frequency: int = Field(default=3, ge=1, le=1000)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_faq_count: int = Field(default=100, ge=1, le=500)


class KnowledgeExtractionResponse(BaseSchema):
    task_id: uuid.UUID
    status: str = "pending"


class SearchItem(BaseSchema):
    id: uuid.UUID
    question: str
    answer: str
    similarity: float
    category: str | None = None


class SearchResponse(BaseSchema):
    query: str
    results: list[SearchItem]
    total: int


class GapItem(BaseSchema):
    id: uuid.UUID | None = None
    question: str
    frequency: int = 1
    priority: Literal["high", "medium", "low"] = "low"
    # 台账状态：open（待处理）/ adopted（已采纳为 FAQ）/ ignored（确认不处理）
    status: Literal["open", "adopted", "ignored"] = "open"
    faq_id: uuid.UUID | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class GapUpdateRequest(BaseSchema):
    status: Literal["open", "adopted", "ignored"]
    faq_id: uuid.UUID | None = None


class GapsSummary(BaseSchema):
    total_gaps: int = 0
    open_gaps: int = 0
    adopted_gaps: int = 0
    ignored_gaps: int = 0
    high_priority: int = 0
    medium_priority: int = 0
    low_priority: int = 0


class GapsResponse(BaseSchema):
    gaps: list[GapItem]
    summary: GapsSummary


class CoverageResponse(BaseSchema):
    """知识覆盖率：最近 N 天的对话里能被现有 FAQ 命中的比例。

    ``method``：``vector``（向量余弦）或 ``trgm``（历史数据无向量时的文本相似度降级）。
    """

    datasource_id: uuid.UUID
    days: int
    threshold: float
    total: int = 0
    covered: int = 0
    rate: float = 0.0
    method: Literal["vector", "trgm"] = "vector"


__all__ = [
    "CoverageResponse",
    "FAQCreate",
    "FAQItem",
    "FAQUpdate",
    "GapItem",
    "GapUpdateRequest",
    "GapsResponse",
    "GapsSummary",
    "KnowledgeExtractionRequest",
    "KnowledgeExtractionResponse",
    "SearchItem",
    "SearchResponse",
]
