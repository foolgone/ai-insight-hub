"""任务接口（API 设计 §10；T11 增加 SSE 进度推送）。"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.pagination import PaginationParams
from app.core.database import SessionLocal, get_db
from app.models import Task, User
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

# SSE 参数：服务端 1s 轮询快照、变化即推；15s 心跳保活
STREAM_POLL_SECONDS = 1.0
STREAM_HEARTBEAT_SECONDS = 15.0
STREAM_LIMIT = 50


def _task_snapshot(task: Task) -> dict[str, Any]:
    """SSE 推送的最小字段集（避免把 result/params 等大字段推给前端）。"""
    return {
        "id": str(task.id),
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress or 0,
        "current_step": task.current_step,
        "error_message": task.error_message,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def _task_snapshots(user: User) -> list[dict[str, Any]]:
    """按用户权限取最近任务快照（admin 看全部，其余只看自己的）。"""
    async with SessionLocal() as session:
        stmt = select(Task).order_by(Task.created_at.desc()).limit(STREAM_LIMIT)
        if user.role != "admin":
            stmt = stmt.where(Task.user_id == user.id)
        rows = list((await session.execute(stmt)).scalars().all())
    return [_task_snapshot(row) for row in rows]


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
    "/stream",
    summary="任务进度 SSE 推送（T11；客户端用 fetch 流式读取）",
    response_class=StreamingResponse,
)
async def stream_tasks(
    request: Request,
    user: User = Depends(require_roles(*READ_ROLES)),
) -> StreamingResponse:
    """SSE 推送任务状态快照：变化即推、15s 心跳、断线由客户端重连。

    说明（MVP）：服务端 1s 查询一次快照，不依赖 Redis pub/sub；
    单连接 1 QPS、连接期间不持有数据库会话；后续可替换为事件驱动实现。
    """

    async def event_stream() -> AsyncIterator[str]:
        last_payload: str | None = None
        idle_seconds = 0.0
        while True:
            if await request.is_disconnected():
                break
            try:
                items = await _task_snapshots(user)
                payload = json.dumps({"items": items}, ensure_ascii=False)
            except Exception:  # noqa: BLE001 - 单次查询失败不中断推送
                payload = last_payload or '{"items": []}'
            if payload != last_payload:
                yield f"event: tasks\ndata: {payload}\n\n"
                last_payload = payload
                idle_seconds = 0.0
            else:
                idle_seconds += STREAM_POLL_SECONDS
                if idle_seconds >= STREAM_HEARTBEAT_SECONDS:
                    yield ": keep-alive\n\n"
                    idle_seconds = 0.0
            await asyncio.sleep(STREAM_POLL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 关闭 Nginx 缓冲，保证逐条推送
        },
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
