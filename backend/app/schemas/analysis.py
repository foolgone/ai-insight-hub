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
    # 洞察是数据源级结果，可能没有单条对话（迁移 012 起 data_id 可空）
    data_id: uuid.UUID | None = None
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


# --------------------------------------------------------------------------- 批次（run）与对比


class RunItem(BaseSchema):
    """一个批次 = 一次任务。``sample_count`` 只统计带 task_id 归属的结果。"""

    task_id: uuid.UUID
    task_type: str
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    sample_count: int = 0
    avg_overall_score: float | None = None
    evaluated: int | None = None
    needs_review: int | None = None


class RunListResponse(BaseSchema):
    items: list[RunItem]


class ScoreBands(BaseSchema):
    """4 档分布（阈值与前端 ``lib/quality.js``、后端 ``quality_level_for`` 一致）。"""

    excellent: int = 0
    good: int = 0
    fair: int = 0
    poor: int = 0


class RunOverview(BaseSchema):
    task_id: uuid.UUID
    status: str
    completed_at: datetime | None = None
    sample_count: int = 0
    avg_overall_score: float = 0.0
    needs_review: int = 0
    dimension_averages: dict[str, float] = Field(default_factory=dict)
    bands: ScoreBands = Field(default_factory=ScoreBands)


class RunDelta(BaseSchema):
    avg_overall_score: float = 0.0
    sample_count: int = 0
    needs_review: int = 0
    dimension_averages: dict[str, float] = Field(default_factory=dict)
    bands: ScoreBands = Field(default_factory=ScoreBands)


class DimensionDelta(BaseSchema):
    name: str
    base: float
    target: float
    delta: float


class DialogueDelta(BaseSchema):
    """同一条对话在两个批次里的分数变化（按 data_id 对齐）。"""

    data_id: uuid.UUID
    base_score: float
    target_score: float
    delta: float


class IssueCategoryDelta(BaseSchema):
    category: str
    label: str
    base: int = 0
    target: int = 0
    delta: int = 0


class RunComparison(BaseSchema):
    """两个批次的对比结果（target 相对 base 的变化）。"""

    base: RunOverview
    target: RunOverview
    delta: RunDelta
    dimensions: list[DimensionDelta]
    # 分数变化最大的几条对话，便于直接定位「改坏了/改好了哪条」
    regressions: list[DialogueDelta]
    improvements: list[DialogueDelta]
    # 只在一侧出现的对话数（批次样本不完全相同时给出，避免误读平均分变化）
    added_items: int = 0
    removed_items: int = 0
    # 问题文本来自 LLM 自由文本，仅做归一化后对比，作为线索而非精确指标
    issues_added: list[str] = Field(default_factory=list)
    issues_removed: list[str] = Field(default_factory=list)
    # 问题分类变化（#6）：可聚合的 TOP 问题类别，比自由文本稳定
    categories: list[IssueCategoryDelta] = Field(default_factory=list)


class IssueCategoryItem(BaseSchema):
    category: str
    label: str
    count: int = 0
    samples: list[str] = Field(default_factory=list)


class IssueCategoriesResponse(BaseSchema):
    """某个评估批次（或最近一次）的问题分类 TOP 列表。"""

    run_id: uuid.UUID | None = None
    total_issues: int = 0
    items: list[IssueCategoryItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- 洞察批次对比（#3）


class InsightMetric(BaseSchema):
    name: str
    base: float = 0.0
    target: float = 0.0
    delta: float = 0.0


class InsightComparison(BaseSchema):
    """两次洞察分析的对比（情感占比 / 意图分布 / 新增与消失的痛点）。"""

    base_task_id: uuid.UUID
    target_task_id: uuid.UUID
    base_completed_at: datetime | None = None
    target_completed_at: datetime | None = None
    sentiment: list[InsightMetric] = Field(default_factory=list)
    intents: list[InsightMetric] = Field(default_factory=list)
    pain_points_added: list[str] = Field(default_factory=list)
    pain_points_removed: list[str] = Field(default_factory=list)


__all__ = [
    "AnalysisResultModel",
    "DialogueDelta",
    "DimensionDelta",
    "EvaluationRequest",
    "EvaluationTaskResponse",
    "InsightComparison",
    "InsightMetric",
    "IssueCategoriesResponse",
    "IssueCategoryDelta",
    "IssueCategoryItem",
    "QualityAnalysisItem",
    "QualityAnalysisListResponse",
    "QualityAnalysisSummary",
    "ReviewRequest",
    "ReviewResponse",
    "RunComparison",
    "RunDelta",
    "RunItem",
    "RunListResponse",
    "RunOverview",
    "ScoreBands",
]
