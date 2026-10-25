"""报告生成 Celery 任务（B-509）。"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.celery import celery_app


@celery_app.task(name="tasks.generate_report")
def generate_report_task(report_id: str) -> dict[str, Any]:
    from app.services.report_service import run_report_task

    return asyncio.run(run_report_task(report_id))


__all__ = ["generate_report_task"]
