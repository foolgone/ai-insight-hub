"""任务接口（API 设计 §10）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.pagination import PaginationParams
from app.core.database import get_db
from app.models import User
from app.schemas.base import Page
from app.schemas.task import (
    TaskCancelResponse,
    TaskListItem,
    TaskResponse,
    TaskRetryResponse,
)
from app.services import task_service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")


@router.get(
    "",
    response_model=Page[TaskListItem],
    response_model_by_alias=False,
    summary="任务列表（分页/过滤）",
)
async def list_tasks(
    params: PaginationParams = Depends(),
    datasource_id: uuid.UUID | None = Query(default=None),
    task_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[TaskListItem]:
    rows, pagination = await task_service.list_tasks(
        session,
        user=user,
        params=params,
        datasource_id=datasource_id,
        task_type=task_type,
        status=status,
    )
    return Page[TaskListItem](
        items=[TaskListItem.model_validate(item) for item in rows],
        pagination=pagination,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    response_model_by_alias=False,
    summary="任务详情/进度",
)
async def get_task(
    task_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task = await task_service.get(session, user=user, task_id=task_id)
    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/cancel",
    response_model=TaskCancelResponse,
    response_model_by_alias=False,
    summary="取消任务",
)
async def cancel_task(
    task_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TaskCancelResponse:
    task = await task_service.cancel(session, user=user, task_id=task_id)
    return TaskCancelResponse(id=task.id, status=task.status, message="Task cancelled successfully")


@router.post(
    "/{task_id}/retry",
    status_code=202,
    response_model=TaskRetryResponse,
    response_model_by_alias=False,
    summary="重试失败任务",
)
async def retry_task(
    task_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TaskRetryResponse:
    task = await task_service.retry(session, user=user, task_id=task_id)
    return TaskRetryResponse(
        id=task.id,
        status=task.status,
        retry_count=task.retry_count or 0,
        message="Task queued for retry",
    )


__all__ = ["router"]
