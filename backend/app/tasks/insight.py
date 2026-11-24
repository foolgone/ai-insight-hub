"""洞察分析 Celery 任务（B-603）。"""
from __future__ import annotations

from typing import Any

from app.core.celery import celery_app
from app.core.async_task import run_task


@celery_app.task(name="tasks.analyze_insights")
def analyze_insights_task(task_id: str) -> dict[str, Any]:
    from app.services.insight_service import run_insight_task

    return run_task(run_insight_task(task_id))


__all__ = ["analyze_insights_task"]
