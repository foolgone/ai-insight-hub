"""质量评估 Celery 任务（B-403）。"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.celery import celery_app


@celery_app.task(name="tasks.evaluate_datasource")
def evaluate_datasource(task_id: str) -> dict[str, Any]:
    """清洗结果质量评估任务入口。"""
    from app.services.evaluation_service import run_evaluation_task

    return asyncio.run(run_evaluation_task(task_id))


__all__ = ["evaluate_datasource"]
