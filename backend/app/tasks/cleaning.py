"""清洗相关 Celery 任务（B-305 骨架，B-313 接入真实清洗 Agent）。"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.celery import celery_app


@celery_app.task(name="tasks.clean_datasource", acks_late=True)
def clean_datasource(task_id: str) -> dict[str, Any]:
    """异步执行清洗（逻辑见 cleaning_service.run_clean_task）。

    ``acks_late=True``：worker 崩溃时任务会被重新投递；清洗本身幂等
    （raw 状态 + cleaned_data 唯一索引），重跑不会产生重复数据。
    """
    from app.services.cleaning_service import run_clean_task

    return asyncio.run(run_clean_task(task_id))


__all__ = ["clean_datasource"]
