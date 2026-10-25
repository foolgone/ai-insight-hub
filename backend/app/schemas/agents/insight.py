"""洞察分析 Agent Schemas（Agent 详细设计 §5）。"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

SENTIMENT_LABELS: tuple[str, ...] = ("正面", "中性", "负面")


class InsightConfig(BaseModel):
    analyze_sentiment: bool = True
    identify_trends: bool = True
    find_pain_points: bool = True


class InsightInput(BaseModel):
    datasource_id: uuid.UUID
    dialogues: list[dict[str, Any]] = Field(default_factory=list)
    time_range: dict[str, str] | None = None
    config: InsightConfig = Field(default_factory=InsightConfig)


class TopQuestion(BaseModel):
    question: str
    count: int = 0
    ratio: float = 0.0


class InsightLLMOutput(BaseModel):
    """LLM 直接返回的结构（情感占比由 Agent 归一化）。"""

    intent_distribution: dict[str, int] = Field(default_factory=dict)
    top_questions: list[TopQuestion] = Field(default_factory=list)
    sentiment_distribution: dict[str, float] = Field(default_factory=dict)
    sentiment_trend: list[dict[str, Any]] = Field(default_factory=list)
    pain_points: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_issues: list[dict[str, Any]] = Field(default_factory=list)
    emerging_topics: list[str] = Field(default_factory=list)


class InsightOutput(BaseModel):
    datasource_id: uuid.UUID
    intent_distribution: dict[str, int]
    top_questions: list[TopQuestion]
    sentiment_distribution: dict[str, float]
    sentiment_trend: list[dict[str, Any]]
    pain_points: list[dict[str, Any]]
    unresolved_issues: list[dict[str, Any]]
    emerging_topics: list[str]
    seasonal_patterns: dict[str, Any] | None = None
    degraded: bool = False
    statistics: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "SENTIMENT_LABELS",
    "InsightConfig",
    "InsightInput",
    "InsightLLMOutput",
    "InsightOutput",
    "TopQuestion",
]
