"""洞察分析 API Schemas（API 设计 §7.3 / §7.4）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InsightRequest(BaseModel):
    time_range: dict[str, str] | None = None
    analyze_sentiment: bool = True
    identify_trends: bool = True
    find_pain_points: bool = True


class InsightTaskResponse(BaseModel):
    task_id: uuid.UUID
    status: str = "pending"


class InsightTopQuestion(BaseModel):
    question: str
    frequency: int = 0
    category: str | None = None


class InsightPainPoint(BaseModel):
    issue: str
    frequency: int = 0
    severity: str | None = None
    suggestions: str | None = None


class InsightResponse(BaseModel):
    datasource_id: uuid.UUID
    status: str = "completed"
    time_range: dict[str, str] | None = None
    intent_distribution: dict[str, int] = Field(default_factory=dict)
    top_questions: list[InsightTopQuestion] = Field(default_factory=list)
    # 情感为 0-1 小数且三类和=1（Agent 设计口径；非百分比）
    sentiment_distribution: dict[str, float] = Field(default_factory=dict)
    sentiment_trend: list[dict[str, Any]] = Field(default_factory=list)
    pain_points: list[InsightPainPoint] = Field(default_factory=list)
    unresolved_issues: list[dict[str, Any]] = Field(default_factory=list)
    emerging_topics: list[str] = Field(default_factory=list)
    seasonal_patterns: dict[str, Any] | None = None
    degraded: bool = False
    created_at: datetime | None = None


__all__ = [
    "InsightPainPoint",
    "InsightRequest",
    "InsightResponse",
    "InsightTaskResponse",
    "InsightTopQuestion",
]
