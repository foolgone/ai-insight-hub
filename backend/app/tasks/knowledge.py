"""知识提取 Celery 任务（B-506）。"""
from __future__ import annotations

from typing import Any

from app.core.celery import celery_app
from app.core.async_task import run_task


@celery_app.task(name="tasks.extract_knowledge")
def extract_knowledge_task(task_id: str) -> dict[str, Any]:
    from app.services.knowledge_service import run_extraction_task

    return run_task(run_extraction_task(task_id))


__all__ = ["extract_knowledge_task"]
