"""清洗编排服务（B-305）。

职责：重复任务护栏、创建 ``tasks`` 记录、入队 Celery、回写 ``celery_task_id``。
真正的清洗逻辑（清洗 Agent）在 B-313/B-314 接入；当前 worker 入口会明确标记失败，
避免任务长期停留在 pending（见 ``run_clean_task``）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TaskAlreadyRunningError
from app.models import RawData, Task, User

ACTIVE_STATUSES = ("pending", "running")
CLEAN_TASK_TYPE = "clean"


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def count_pending_records(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(RawData)
            .where(
                RawData.datasource_id == datasource_id,
                RawData.status == "pending",
            )
        )
        or 0
    )


async def ensure_no_running_task(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    task_type: str = CLEAN_TASK_TYPE,
) -> None:
    """同数据源同类任务在跑 → 409 TASK_ALREADY_RUNNING。"""
    running = int(
        await session.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.datasource_id == datasource_id,
                Task.task_type == task_type,
                Task.status.in_(ACTIVE_STATUSES),
            )
        )
        or 0
    )
    if running:
        raise TaskAlreadyRunningError(
            details={"datasource_id": str(datasource_id), "task_type": task_type}
        )


async def create_clean_task(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    task_name: str,
    params: dict[str, Any],
) -> Task:
    task = Task(
        task_type=CLEAN_TASK_TYPE,
        task_name=task_name,
        datasource_id=datasource_id,
        user_id=user.id,
        params=params,
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


def enqueue_clean(task: Task) -> str:
    """提交 Celery 任务并返回 celery task id（测试可 monkeypatch）。"""
    from app.tasks.cleaning import clean_datasource

    result = clean_datasource.delay(str(task.id))
    return str(result.id)


async def run_clean_task(task_id: str) -> dict[str, Any]:
    """Celery worker 入口（B-305 骨架）。

    B-313 会替换为真实清洗 Agent 调用；在此之前，把任务显式标记为 failed，
    避免任务永久处于 pending/running。
    """
    from app.core.database import SessionLocal

    async with SessionLocal() as session:
        task = await session.get(Task, uuid.UUID(task_id))
        if task is None:
            return {"status": "missing", "task_id": task_id}
        task.status = "failed"
        task.current_step = "waiting_for_cleaning_agent"
        task.error_message = "Cleaning agent is not available yet (B-313/B-314)"
        task.completed_at = _now_naive()
        await session.commit()
        return {"status": "failed", "task_id": task_id}


__all__ = [
    "ACTIVE_STATUSES",
    "CLEAN_TASK_TYPE",
    "count_pending_records",
    "create_clean_task",
    "enqueue_clean",
    "ensure_no_running_task",
    "run_clean_task",
]
