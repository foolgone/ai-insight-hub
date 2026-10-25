"""任务 Schemas（API 设计 §10）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.base import BaseSchema, ORMSchema

TaskType = Literal["clean", "evaluate", "extract", "analyze", "report"]
TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class TaskListItem(ORMSchema):
    """任务列表项（API §10.2）。"""

    id: uuid.UUID
    task_type: str
    status: str
    progress: int | None = None
    duration: float | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class TaskResponse(ORMSchema):
    """任务详情（API §10.1）。"""

    id: uuid.UUID
    task_type: str
    task_name: str | None = None
    status: str
    progress: int | None = None
    current_step: str | None = None
    datasource_id: uuid.UUID | None = None
    params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None
    retry_count: int | None = None
    max_retries: int | None = None
    created_at: datetime | None = None
    # 由 API 设计给出、但未落库：保留字段以便前端契约一致（当前恒为 None）
    estimated_completion: datetime | None = None


class TaskCancelResponse(BaseSchema):
    id: uuid.UUID
    status: str
    message: str


class TaskRetryResponse(BaseSchema):
    id: uuid.UUID
    status: str
    retry_count: int
    message: str


__all__ = [
    "TaskCancelResponse",
    "TaskListItem",
    "TaskResponse",
    "TaskRetryResponse",
    "TaskStatus",
    "TaskType",
]
