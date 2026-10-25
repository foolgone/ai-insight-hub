"""知识提取 Celery 任务（B-506）。"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.celery import celery_app


@celery_app.task(name="tasks.extract_knowledge")
def extract_knowledge_task(task_id: str) -> dict[str, Any]:
    from app.services.knowledge_service import run_extraction_task

    return asyncio.run(run_extraction_task(task_id))


__all__ = ["extract_knowledge_task"]
