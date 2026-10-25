"""Celery 应用（B-303）。

- broker / backend 复用 Redis（db 1 / db 2，见 ``settings.CELERY_*``）；
- 测试与本地联调可用 ``CELERY_TASK_ALWAYS_EAGER=true`` 同步执行，无需启动 worker；
- 任务模块统一放 ``app/tasks``（通过 ``include`` 自动发现）。
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

TASK_MODULES = ["app.tasks"]

celery_app = Celery(
    "aiinsight",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=TASK_MODULES,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=1700,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
)


__all__ = ["TASK_MODULES", "celery_app"]
