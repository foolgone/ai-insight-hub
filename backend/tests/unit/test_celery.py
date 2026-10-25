"""B-303 Celery 基础设施测试（eager 模式，不依赖 worker/broker）。"""
from __future__ import annotations

import pytest

from app.core.celery import celery_app
from app.tasks import ping

pytestmark = pytest.mark.unit


@pytest.fixture()
def eager_mode():
    previous = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        yield
    finally:
        celery_app.conf.task_always_eager = previous


def test_celery_configuration() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert "tasks.ping" in celery_app.tasks


def test_ping_runs_in_eager_mode(eager_mode) -> None:
    result = ping.delay()

    assert result.get(timeout=5) == "pong"
