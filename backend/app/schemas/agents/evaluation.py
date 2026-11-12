"""质量评估 Agent Schemas（Agent 详细设计 §3）。

- 5 维固定：accuracy / completeness / hallucination / tone / compliance；
- 权重：0.35 / 0.25 / 0.20 / 0.10 / 0.10（总分 = Σ(维度分×权重)/Σ(启用维度权重)）；
- 分数 0-100；阈值默认 70（低于 70 → needs_review）；
- 质量分级：≥90 excellent / ≥75 good / ≥60 fair / <60 poor。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DimensionName = Literal["accuracy", "completeness", "hallucination", "tone", "compliance"]

# 问题分类（#6）：把自由文本 issue 归到可聚合的类别，支撑「TOP5 问题」与批次对比
IssueCategory = Literal[
    "hallucination",
    "missing_knowledge",
    "accuracy",
    "tone",
    "compliance",
    "process",
    "other",
]

ISSUE_CATEGORY_LABELS: dict[str, str] = {
    "hallucination": "幻觉/编造",
    "missing_knowledge": "知识缺失",
    "accuracy": "事实不准",
    "tone": "话术/语气",
    "compliance": "合规风险",
    "process": "流程/时效",
    "other": "其他",
}

# 模型没给分类时的兜底映射（按维度归因）
DIMENSION_TO_CATEGORY: dict[str, str] = {
    "accuracy": "accuracy",
    "completeness": "missing_knowledge",
    "hallucination": "hallucination",
    "tone": "tone",
    "compliance": "compliance",
}

DIMENSION_NAMES: tuple[DimensionName, ...] = (
    "accuracy",
    "completeness",
    "hallucination",
    "tone",
    "compliance",
)

DIMENSION_WEIGHTS: dict[str, float] = {
    "accuracy": 0.35,
    "completeness": 0.25,
    "hallucination": 0.20,
    "tone": 0.10,
    "compliance": 0.10,
}

DIMENSION_LABELS: dict[str, str] = {
    "accuracy": "准确性",
    "completeness": "完整性",
    "hallucination": "幻觉检测",
    "tone": "语气",
    "compliance": "合规性",
}

EVALUATION_THRESHOLD = 70.0
EMPTY_KNOWLEDGE_HALLUCINATION_SCORE = 70.0


class DimensionScore(BaseModel):
    score: float = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)


class IssueItem(BaseModel):
    """一条可聚合的问题（分类 + 维度 + 原文描述）。"""

    category: IssueCategory = "other"
    dimension: DimensionName | None = None
    detail: str = ""


class EvaluationConfig(BaseModel):
    dimensions: list[DimensionName] = Field(default_factory=lambda: list(DIMENSION_NAMES))
    threshold: float = Field(default=EVALUATION_THRESHOLD, ge=0, le=100)

    @field_validator("dimensions")
    @classmethod
    def _validate_dimensions(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("dimensions must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("dimensions must not contain duplicates")
        return value


class EvaluationInput(BaseModel):
    dialogue: dict[str, Any]
    knowledge_base: list[dict[str, Any]] = Field(default_factory=list)
    config: EvaluationConfig = Field(default_factory=EvaluationConfig)


class EvaluationLLMOutput(BaseModel):
    """LLM 直接返回的结构（后续由 Agent 计算总分/复核/分级）。"""

    dimensions: dict[str, DimensionScore]
    suggestions: list[str] = Field(default_factory=list)
    # 问题分类（可选）：模型按 category 归类；缺失时按维度兜底映射
    issue_items: list[IssueItem] = Field(default_factory=list)


class QualityLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class EvaluationOutput(BaseModel):
    dialogue_id: str
    overall_score: float
    dimensions: dict[str, DimensionScore]
    has_issues: bool
    critical_issues: list[str]
    minor_issues: list[str]
    suggestions: list[str]
    quality_level: QualityLevel
    needs_review: bool
    # 分类后的问题清单（聚合 TOP 问题 / 批次对比用）
    issue_items: list[IssueItem] = Field(default_factory=list)


__all__ = [
    "DIMENSION_LABELS",
    "DIMENSION_NAMES",
    "DIMENSION_TO_CATEGORY",
    "DIMENSION_WEIGHTS",
    "EMPTY_KNOWLEDGE_HALLUCINATION_SCORE",
    "EVALUATION_THRESHOLD",
    "ISSUE_CATEGORY_LABELS",
    "DimensionScore",
    "EvaluationConfig",
    "EvaluationInput",
    "EvaluationLLMOutput",
    "EvaluationOutput",
    "IssueCategory",
    "IssueItem",
    "QualityLevel",
]
