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
# D-11 降级口径：MVP 只生成 markdown / excel；pdf/html 返回 422
SUPPORTED_FORMATS: tuple[str, ...] = ("markdown", "excel")

REPORT_TYPE_LABELS = {
    "quality": "质量分析报告",
    "knowledge": "知识库报告",
    "insight": "洞察报告",
    "comprehensive": "综合分析报告",
}


class ReportSection(BaseModel):
    title: str = Field(min_length=1)
    content: str = ""


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
]
