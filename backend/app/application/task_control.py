"""任务控制（轻量状态查询）。

从 ``services/task_service`` 抽出，供 worker 循环内检查取消状态。
放在应用层是为了让业务服务依赖它、而不是反向依赖 ``task_service``，
从而消除「服务 ↔ 任务服务」的循环依赖。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task

__all__ = ["is_cancelled"]


async def is_cancelled(session: AsyncSession, task_id: uuid.UUID) -> bool:
    """轻量查询任务是否已被取消（绕开身份映射缓存）。"""
    status = await session.scalar(select(Task.status).where(Task.id == task_id))
    return status == "cancelled"
