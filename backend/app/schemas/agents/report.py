"""报告生成 Agent Schemas（Agent 详细设计 §5）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

REPORT_TYPES: tuple[str, ...] = (
    "quality",
    "knowledge",
    "insight",
    "comprehensive",
)
REPORT_FORMATS: tuple[str, ...] = ("markdown", "excel", "pdf", "html")
# T8：MVP 生成 markdown / excel / pdf；html 仍返回 422
SUPPORTED_FORMATS: tuple[str, ...] = ("markdown", "excel", "pdf")

REPORT_TYPE_LABELS = {
    "quality": "质量分析报告",
    "knowledge": "知识库报告",
    "insight": "洞察报告",
    "comprehensive": "综合分析报告",
}


class ReportSection(BaseModel):
    title: str = Field(min_length=1)
    content: str = ""


class RunComparisonSide(BaseModel):
    """报告 Run 对比章节的一侧 Run 元数据（前端快照）。"""

    run_id: str = Field(min_length=1)
    dataset_name: str | None = None
    dataset_version_id: str | None = None
    execution_mode: str | None = None
    adapter: str | None = None
    top_k: int | None = None
    completed_at: str | None = None
    judge_model: str | None = None
    prompt_version: str | None = None
    total_items: int | None = None
    evaluated_items: int | None = None
    invalid_items: int | None = None
    failed_items: int | None = None
    skipped_items: int | None = None
    unprocessed_items: int | None = None


class RunComparisonMetric(BaseModel):
    metric_name: str = Field(min_length=1)
    metric_short: str | None = None
    label: str | None = None
    base: float | None = None
    target: float | None = None
    delta: float | None = None


class RunComparisonCase(BaseModel):
    dataset_item_id: str = Field(min_length=1)
    item_key: str | None = None
    question: str | None = None
    verdict: str = "unprocessed"
    driver_metric: str | None = None
    driver_delta: float | None = None
    note: str | None = None


class RunComparisonSummary(BaseModel):
    improved: int = 0
    regressed: int = 0
    unchanged: int = 0
    invalid: int = 0
    unprocessed: int = 0
    total: int = 0
    aligned_total: int = 0
    exported_cases: int = 0
    case_truncated: bool = False
    truncation_note: str | None = None


class RunComparisonPayload(BaseModel):
    """对比页生成的 Run 对比快照（P1-3b 报告章节）。"""

    base: RunComparisonSide
    target: RunComparisonSide
    metrics: list[RunComparisonMetric] = Field(default_factory=list)
    case_summary: RunComparisonSummary = Field(default_factory=RunComparisonSummary)
    top_improved: list[RunComparisonCase] = Field(default_factory=list)
    top_regressed: list[RunComparisonCase] = Field(default_factory=list)
    same_config: bool = False
    compare_url: str | None = None


class ReportLLMOutput(BaseModel):
    """LLM 直接返回的结构（generated_at 等由 Agent 补齐）。"""

    summary: str = ""
    sections: list[ReportSection] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ReportConfig(BaseModel):
    include_charts: bool = True
    include_recommendations: bool = True
    time_range: dict[str, str] | None = None
    run_comparison: RunComparisonPayload | None = None


class ReportInput(BaseModel):
    datasource_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    report_type: Literal["quality", "knowledge", "insight", "comprehensive"]
    data: dict[str, Any] = Field(default_factory=dict)
    config: ReportConfig = Field(default_factory=ReportConfig)


class ReportOutput(BaseModel):
    title: str
    report_type: str
    generated_at: datetime
    summary: str
    sections: list[ReportSection]
    highlights: list[str]
    recommendations: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "REPORT_FORMATS",
    "REPORT_TYPE_LABELS",
    "REPORT_TYPES",
    "SUPPORTED_FORMATS",
    "ReportConfig",
    "ReportInput",
    "ReportLLMOutput",
    "ReportOutput",
    "ReportSection",
    "RunComparisonCase",
    "RunComparisonMetric",
    "RunComparisonPayload",
    "RunComparisonSide",
    "RunComparisonSummary",
]
