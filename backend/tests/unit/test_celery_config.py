"""Celery 可用性配置单测（重投递 / 预取 / 队列隔离）。"""
from __future__ import annotations

import pytest

from app.core.celery import celery_app
from app.tasks.cleaning import clean_datasource

pytestmark = pytest.mark.unit


def test_worker_reliability_config() -> None:
    conf = celery_app.conf

    # 默认 at-most-once：非幂等任务不开启 acks_late
    assert conf.task_acks_late is False
    # worker 被杀时把任务退回队列（对 acks_late 任务生效）
    assert conf.task_reject_on_worker_lost is True
    # 长任务场景不预取，避免任务囤积
    assert conf.worker_prefetch_multiplier == 1
    # 可见性超时必须大于任务硬超时，否则会被重复投递
    assert conf.broker_transport_options["visibility_timeout"] > conf.task_time_limit


def test_clean_task_is_acked_late_and_routed() -> None:
    # 清洗幂等，允许崩溃后重投递
    assert clean_datasource.acks_late is True
    assert celery_app.conf.task_routes["tasks.clean_datasource"]["queue"] == "clean"
    assert celery_app.conf.task_default_queue == "default"
