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

    result = asyncio.run(run_clean_task(task_id))

    # 转写与切分已拆成两个任务：转写完成后自动串接切分（用户仍是一步操作）
    for structure_task_id in result.get("structure_task_ids") or []:
        try:
            from app.tasks.structure import structure_raw

            structure_raw.delay(structure_task_id)
        except Exception:  # noqa: BLE001 - 入队失败不影响清洗结果，可手动重试
            import logging

            logging.getLogger(__name__).exception(
                "enqueue structure task failed: %s", structure_task_id
            )
    return result


__all__ = ["clean_datasource"]
