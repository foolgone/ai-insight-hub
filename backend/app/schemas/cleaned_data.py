"""清洗结果 Schemas（API 设计 §6.3 / §6.4）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import ORMSchema


class CleanedDataItem(ORMSchema):
    """清洗结果列表项（含 ``id``，供详情端点使用）。"""

    id: uuid.UUID
    dialogue_id: uuid.UUID
    timestamp: datetime | None = None
    user_message: str
    ai_response: str
    quality_score: float | None = None
    issues: list[str] | None = None
    # ORM 属性为 metadata_（metadata 是 SQLAlchemy 保留名），响应字段仍为 metadata
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")


class CleanedDataDetail(CleanedDataItem):
    """清洗结果详情（附 Agent 执行信息）。"""

    datasource_id: uuid.UUID
    agent_version: str | None = None
    processing_duration: float | None = None
    token_usage: dict[str, Any] | None = None
    created_at: datetime | None = None


__all__ = ["CleanedDataDetail", "CleanedDataItem"]
