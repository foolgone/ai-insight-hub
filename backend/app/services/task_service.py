"""任务服务（API 设计 §10，5 态状态机）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_owner
from app.api.pagination import PaginationParams, paginate
from app.core.exceptions import (
    TaskNotCancellableError,
    TaskNotFoundError,
    TaskNotRetryableError,
)
from app.models import Task, User
from app.schemas.base import Pagination

CANCELLABLE_STATUSES = {"pending", "running"}
_SORTABLE = {"created_at": Task.created_at, "status": Task.status}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_or_404(session: AsyncSession, task_id: uuid.UUID, user: User) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(details={"task_id": str(task_id)})
    assert_owner(task.user_id, user)
    return task


async def list_tasks(
    session: AsyncSession,
    *,
    user: User,
    params: PaginationParams,
    datasource_id: uuid.UUID | None = None,
    task_type: str | None = None,
    status: str | None = None,
) -> tuple[list[Task], Pagination]:
    stmt = select(Task)
    if user.role != "admin":
        stmt = stmt.where(Task.user_id == user.id)
    if datasource_id is not None:
        stmt = stmt.where(Task.datasource_id == datasource_id)
    if task_type:
        stmt = stmt.where(Task.task_type == task_type)
    if status:
        stmt = stmt.where(Task.status == status)
    return await paginate(session, stmt, params, sortable=_SORTABLE)


async def get(session: AsyncSession, *, user: User, task_id: uuid.UUID) -> Task:
    return await _get_or_404(session, task_id, user)


async def cancel(session: AsyncSession, *, user: User, task_id: uuid.UUID) -> Task:
    task = await _get_or_404(session, task_id, user)
    if task.status not in CANCELLABLE_STATUSES:
        raise TaskNotCancellableError(details={"status": task.status})

    task.status = "cancelled"
    task.completed_at = _now_naive()
    await session.flush()
    await session.refresh(task)
    return task


async def retry(session: AsyncSession, *, user: User, task_id: uuid.UUID) -> Task:
    task = await _get_or_404(session, task_id, user)
    if task.status != "failed":
        raise TaskNotRetryableError(details={"status": task.status})

    task.status = "pending"
    task.progress = 0
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    task.retry_count = (task.retry_count or 0) + 1
    await session.flush()
    await session.refresh(task)
    return task


__all__ = ["CANCELLABLE_STATUSES", "cancel", "get", "list_tasks", "retry"]
