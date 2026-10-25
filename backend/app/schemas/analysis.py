"""分析与评估 Schemas（API 设计 §7）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.agents.evaluation import EvaluationConfig
from app.schemas.base import BaseSchema, Pagination


class EvaluationRequest(BaseSchema):
    data_ids: list[uuid.UUID] = Field(default_factory=list)
    config: EvaluationConfig = Field(default_factory=EvaluationConfig)


class EvaluationTaskResponse(BaseSchema):
    task_id: uuid.UUID
    estimated_duration: float
    message: str


class QualityAnalysisItem(BaseSchema):
    id: uuid.UUID
    data_id: uuid.UUID
    overall_score: float
    needs_review: bool
    quality_level: str | None = None
    dimensions: dict[str, Any] = Field(default_factory=dict)
    agent_name: str
    agent_version: str | None = None
    created_at: datetime | None = None


class QualityAnalysisSummary(BaseSchema):
    total: int = 0
    avg_overall_score: float = 0.0
    needs_review_count: int = 0
    dimension_averages: dict[str, float] = Field(default_factory=dict)


class QualityAnalysisListResponse(BaseSchema):
    items: list[QualityAnalysisItem]
    pagination: Pagination
    summary: QualityAnalysisSummary


class ReviewRequest(BaseSchema):
    decision: Literal["approved", "rejected", "corrected"]
    note: str | None = Field(default=None, max_length=1000)
    corrected_scores: dict[str, float] | None = None


class ReviewResponse(BaseSchema):
    id: uuid.UUID
    needs_review: bool
    decision: str
    message: str


class AnalysisResultModel(BaseModel):
    """``analysis_results.result`` JSON 的结构化视图（评估类型）。"""

    overall_score: float = 0
    dimensions: dict[str, Any] = Field(default_factory=dict)
    needs_review: bool = False
    quality_level: str | None = None
    suggestions: list[str] = Field(default_factory=list)


__all__ = [
    "AnalysisResultModel",
    "EvaluationRequest",
    "EvaluationTaskResponse",
    "QualityAnalysisItem",
    "QualityAnalysisListResponse",
    "QualityAnalysisSummary",
    "ReviewRequest",
    "ReviewResponse",
]
