"""知识提取 Agent Schemas（Agent 详细设计 §4）。"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_MAX_FAQS = 20
DEFAULT_MIN_CONFIDENCE = 0.5
MAX_DIALOGUES_PER_RUN = 50


class ExtractedFAQ(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    category: str = "general"
    variations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_dialogue_ids: list[str] = Field(default_factory=list)


class KnowledgeGap(BaseModel):
    question: str = Field(min_length=1)
    reason: str | None = None
    frequency: int = Field(default=1, ge=1)


class ExtractionConfig(BaseModel):
    max_faqs: int = Field(default=DEFAULT_MAX_FAQS, ge=1, le=100)
    min_confidence: float = Field(default=DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0)
    include_gaps: bool = True


class ExtractionInput(BaseModel):
    datasource_id: uuid.UUID
    dialogues: list[dict[str, Any]] = Field(default_factory=list)
    existing_questions: list[str] = Field(default_factory=list)
    config: ExtractionConfig = Field(default_factory=ExtractionConfig)


class ExtractionLLMOutput(BaseModel):
    """LLM 直接返回的结构（embeddings 由 Agent 计算）。"""

    faqs: list[ExtractedFAQ] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)


class ExtractedFAQWithEmbedding(ExtractedFAQ):
    embedding: list[float] | None = None


class ExtractionOutput(BaseModel):
    datasource_id: uuid.UUID
    faqs: list[ExtractedFAQWithEmbedding]
    gaps: list[KnowledgeGap]
    stats: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "DEFAULT_MAX_FAQS",
    "DEFAULT_MIN_CONFIDENCE",
    "MAX_DIALOGUES_PER_RUN",
    "ExtractedFAQ",
    "ExtractedFAQWithEmbedding",
    "ExtractionConfig",
    "ExtractionInput",
    "ExtractionLLMOutput",
    "ExtractionOutput",
    "KnowledgeGap",
]
