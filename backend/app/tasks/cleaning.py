"""清洗相关 Celery 任务（B-305 骨架，B-313 接入真实清洗 Agent）。"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.celery import celery_app


@celery_app.task(name="tasks.clean_datasource")
def clean_datasource(task_id: str) -> dict[str, Any]:
    """异步执行清洗（当前为骨架实现，逻辑见 cleaning_service.run_clean_task）。"""
    from app.services.cleaning_service import run_clean_task

    return asyncio.run(run_clean_task(task_id))


__all__ = ["clean_datasource"]
