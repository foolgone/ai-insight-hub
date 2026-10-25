"""报告 Schemas（API 设计 §9）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.agents.report import ReportConfig
from app.schemas.base import BaseSchema, ORMSchema


class ReportCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=255)
    # 枚举由服务层校验（非法值返回 422 REPORT_FORMAT_INVALID，而非通用 VALIDATION_ERROR）
    report_type: str
    format: str
    config: ReportConfig = Field(default_factory=ReportConfig)


class ReportCreateResponse(BaseSchema):
    id: uuid.UUID
    title: str
    report_type: str
    format: str
    status: str
    created_at: datetime | None = None


class ReportItem(ORMSchema):
    id: uuid.UUID
    title: str
    report_type: str
    format: str
    status: str
    file_url: str | None = None
    file_size: int | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class ReportDetail(ReportItem):
    datasource_id: uuid.UUID
    generation_duration: float | None = None
    view_count: int | None = None
    download_count: int | None = None
    expires_at: datetime | None = None
    error_message: str | None = None
    data: dict[str, Any] | None = None


__all__ = [
    "ReportCreate",
    "ReportCreateResponse",
    "ReportDetail",
    "ReportItem",
]
