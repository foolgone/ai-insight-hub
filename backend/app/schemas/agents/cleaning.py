"""数据清洗 Agent Schemas（Agent 详细设计 §2）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class CleaningState(str, Enum):
    """清洗状态机（6 态 + 失败）。"""

    PENDING = "pending"
    PARSING = "parsing"
    DEDUPLICATING = "deduplicating"
    NORMALIZING = "normalizing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class CleaningConfig(BaseModel):
    remove_duplicates: bool = True
    normalize_text: bool = True
    dedup_threshold: float = Field(default=0.95, ge=0.0, le=1.0)


class CleaningInput(BaseModel):
    datasource_id: uuid.UUID
    raw_data: str
    data_type: Literal["csv", "json", "txt"] = "csv"
    config: CleaningConfig = Field(default_factory=CleaningConfig)


class CleanedDialogue(BaseModel):
    dialogue_id: str
    timestamp: datetime | None = None
    user_message: str = ""
    ai_response: str = ""
    quality_score: float = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)


class CleaningStatistics(BaseModel):
    total_records: int = 0
    cleaned_records: int = 0
    failed_records: int = 0
    avg_quality_score: float = 0.0


class CleaningOutput(BaseModel):
    """清洗结果（计数由 Agent 依据 dialogues 重算，保证一致）。"""

    datasource_id: uuid.UUID | None = None
    total_records: int = 0
    cleaned_records: int = 0
    failed_records: int = 0
    dialogues: list[CleanedDialogue] = Field(default_factory=list)
    statistics: CleaningStatistics = Field(default_factory=CleaningStatistics)


__all__ = [
    "CleanedDialogue",
    "CleaningConfig",
    "CleaningInput",
    "CleaningOutput",
    "CleaningState",
    "CleaningStatistics",
]
