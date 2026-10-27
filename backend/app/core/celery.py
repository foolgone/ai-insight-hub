"""Celery 应用（B-303）。

- broker / backend 复用 Redis（db 1 / db 2，见 ``settings.CELERY_*``）；
- 测试与本地联调可用 ``CELERY_TASK_ALWAYS_EAGER=true`` 同步执行，无需启动 worker；
- 任务模块统一放 ``app/tasks``（通过 ``include`` 自动发现）。
"""
from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init
from celery.schedules import crontab

from loguru import logger

from app.core import metrics  # noqa: F401  注册 Worker 侧 Prometheus 指标
from app.core.config import settings

TASK_MODULES = ["app.tasks"]


@worker_process_init.connect
def _start_worker_metrics(**_kwargs: object) -> None:
    """在 worker 子进程启动 Prometheus HTTP server（仅 WORKER_METRICS_ENABLED）。"""
    if not settings.WORKER_METRICS_ENABLED:
        return
    try:
        from prometheus_client import start_http_server

        start_http_server(settings.WORKER_METRICS_PORT)
        logger.info("worker metrics server started port={}", settings.WORKER_METRICS_PORT)
    except Exception as exc:  # noqa: BLE001 - 可观测失败不影响任务
        logger.warning("worker metrics server failed: {}", exc)


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
    # B-608：每日成本对账/告警（成本只认 llm_calls 聚合）
    beat_schedule={
        "daily-cost-monitor": {
            "task": "tasks.monitor_cost",
            "schedule": crontab(hour=0, minute=5),
        },
    },
)


__all__ = ["TASK_MODULES", "celery_app"]
