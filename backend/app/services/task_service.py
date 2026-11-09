"""任务服务（API 设计 §10，5 态状态机）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.api.deps import assert_owner
from app.api.pagination import PaginationParams, paginate
from app.application import executors, task_control
from app.core.exceptions import (
    TaskNotCancellableError,
    TaskNotFoundError,
    TaskNotRetryableError,
)
from app.models import Report, Task, User
from app.schemas.base import Pagination

CANCELLABLE_STATUSES = {"pending", "running"}
_SORTABLE: dict[str, InstrumentedAttribute] = {
    "created_at": Task.created_at,
    "status": Task.status,
}


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


async def is_cancelled(session: AsyncSession, task_id: uuid.UUID) -> bool:
    """兼容入口：实现已移到 ``application/task_control``。"""
    return await task_control.is_cancelled(session, task_id)


def _revoke(celery_task_id: str) -> None:
    """撤销排队中的 Celery 任务（不 terminate，避免中断正在写库的事务）。"""
    try:
        from app.core.celery import celery_app

        celery_app.control.revoke(celery_task_id, terminate=False)
    except Exception as exc:  # noqa: BLE001 - broker 不可用不应阻塞取消
        logger.warning("celery revoke failed task_id={} error={}", celery_task_id, exc)


async def _dispatch_retry(session: AsyncSession, task: Task) -> str:
    """按 task_type 重新入队，返回新的 celery task id。

    执行器注册表集中在 ``application/executors``，这里不再反向 import 各业务服务。
    """
    executor = executors.get_executor(task.task_type)
    if executor is None:
        raise TaskNotRetryableError(
            details={"task_type": task.task_type, "reason": "unsupported_type"}
        )
    return await executor(session, task)


async def cancel(session: AsyncSession, *, user: User, task_id: uuid.UUID) -> Task:
    task = await _get_or_404(session, task_id, user)
    if task.status not in CANCELLABLE_STATUSES:
        raise TaskNotCancellableError(details={"status": task.status})

    task.status = "cancelled"
    task.completed_at = _now_naive()

    # 报告任务：同步把报告置为失败，避免前端一直显示 generating
    if task.task_type == "report":
        report_id = (task.params or {}).get("report_id")
        if report_id:
            report = await session.get(Report, uuid.UUID(str(report_id)))
            if report is not None and report.status == "generating":
                report.status = "failed"
                report.error_message = "cancelled by user"
                report.completed_at = _now_naive()

    if task.celery_task_id:
        _revoke(task.celery_task_id)

    await session.flush()
    await session.refresh(task)
    return task


async def retry(session: AsyncSession, *, user: User, task_id: uuid.UUID) -> Task:
    task = await _get_or_404(session, task_id, user)
    if task.status != "failed":
        raise TaskNotRetryableError(details={"status": task.status})

    # 清理上一次的残留状态，避免前端看到旧进度/旧结果
    task.status = "pending"
    task.progress = 0
    task.current_step = None
    task.result = None
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    task.retry_count = (task.retry_count or 0) + 1

    # 真正重新入队（此前只改状态，任务永不执行）
    task.celery_task_id = await _dispatch_retry(session, task)

    await session.flush()
    await session.refresh(task)
    return task


__all__ = ["CANCELLABLE_STATUSES", "cancel", "get", "is_cancelled", "list_tasks", "retry"]
