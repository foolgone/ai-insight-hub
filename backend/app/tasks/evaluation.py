"""质量评估 Celery 任务（B-403）。"""
from __future__ import annotations

from typing import Any

from app.core.celery import celery_app
from app.core.async_task import run_task


@celery_app.task(name="tasks.evaluate_datasource")
def evaluate_datasource(task_id: str) -> dict[str, Any]:
    """清洗结果质量评估任务入口。"""
    from app.services.evaluation_service import run_evaluation_task

    return run_task(run_evaluation_task(task_id))


__all__ = ["evaluate_datasource"]
