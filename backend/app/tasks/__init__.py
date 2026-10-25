"""Celery 任务注册入口（通过 ``celery_app`` 的 ``include`` 自动发现）。"""
from __future__ import annotations

from app.core.celery import celery_app


@celery_app.task(name="tasks.ping")
def ping() -> str:
    """健康检查任务：验证 broker/worker 链路（B-303）。"""
    return "pong"


# 导入子模块以完成任务注册（Celery include 只加载本包）
from app.tasks import (  # noqa: E402,F401
    cleaning,
    cost_monitor,
    evaluation,
    insight,
    knowledge,
    report,
)

__all__ = ["ping"]
