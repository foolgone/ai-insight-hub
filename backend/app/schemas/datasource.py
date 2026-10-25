"""数据源 Schemas（API 设计 §5）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import BaseSchema, ORMSchema

EVALUATION_DIMENSIONS = (
    "accuracy",
    "completeness",
    "tone",
    "compliance",
    "hallucination",
)

DataSourceType = Literal["customer_service", "sales", "support", "other"]
DataSourceStatus = Literal["active", "archived", "processing", "error"]


class DataSourceConfig(BaseSchema):
    """数据源配置（config JSONB 的结构化视图）。"""

    auto_clean: bool = True
    auto_evaluate: bool = True
    evaluation_dimensions: list[str] = Field(default_factory=lambda: list(EVALUATION_DIMENSIONS))
    notification_email: EmailStr | None = None

    @field_validator("evaluation_dimensions")
    @classmethod
    def _validate_dimensions(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in EVALUATION_DIMENSIONS]
        if invalid:
            raise ValueError(f"unsupported evaluation dimensions: {invalid}")
        if not value:
            raise ValueError("evaluation_dimensions must not be empty")
        return value


class DataSourceCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    type: DataSourceType
    config: DataSourceConfig = Field(default_factory=DataSourceConfig)
    # 创建时可选初始化 12 条种子知识（B-502 冷启动）
    init_seed_knowledge: bool = False


class DataSourceUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    config: DataSourceConfig | None = None


class DataSourceStatistics(BaseSchema):
    total_records: int = 0
    cleaned_records: int = 0
    quality_score_avg: float = 0.0
    last_processed_at: datetime | None = None


class DataSourceItem(ORMSchema):
    """列表项（API §5.2）。"""

    id: uuid.UUID
    name: str
    type: str
    status: str
    statistics: DataSourceStatistics | None = None
    created_at: datetime | None = None


class DataSourceResponse(ORMSchema):
    """详情/创建响应（API §5.1 / §5.3）。"""

    id: uuid.UUID
    name: str
    description: str | None = None
    type: str
    status: str
    config: DataSourceConfig | None = None
    statistics: DataSourceStatistics | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DataSourceUpdateResponse(BaseSchema):
    """更新响应（API §5.4 只返回变更摘要）。"""

    id: uuid.UUID
    name: str
    description: str | None = None
    updated_at: datetime | None = None


class DataSourceDeleteResponse(BaseSchema):
    message: str
    deleted_records: int


__all__ = [
    "EVALUATION_DIMENSIONS",
    "DataSourceConfig",
    "DataSourceCreate",
    "DataSourceDeleteResponse",
    "DataSourceItem",
    "DataSourceResponse",
    "DataSourceStatistics",
    "DataSourceStatus",
    "DataSourceType",
    "DataSourceUpdate",
    "DataSourceUpdateResponse",
]
