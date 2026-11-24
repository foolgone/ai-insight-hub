"""切分任务（转写之后的第二步，可独立重试）。"""
from __future__ import annotations

from typing import Any

from app.core.celery import celery_app
from app.core.async_task import run_task


@celery_app.task(name="tasks.structure_raw")
def structure_raw(task_id: str) -> dict[str, Any]:
    """对单个音视频文件的转写文本做分块切分（替换该文件的对话结果）。"""
    from app.services.structure_task_service import run_structure_task

    return run_task(run_structure_task(task_id))


__all__ = ["structure_raw"]
