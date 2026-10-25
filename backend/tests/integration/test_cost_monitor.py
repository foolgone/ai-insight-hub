"""B-608 成本监控任务集成测试。"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.cost_tracker import CostTracker
from app.core.llm import LLMResponse, LLMUsage
from app.tasks.cost_monitor import run_cost_monitor

pytestmark = pytest.mark.integration


def _response(tokens: int = 1_000_000) -> LLMResponse:
    return LLMResponse(
        content="",
        usage=LLMUsage(input_tokens=tokens, output_tokens=0),
        model="deepseek-flash",
        latency_ms=10.0,
    )


async def test_cost_monitor_alerts_when_limit_exceeded(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_MTOK", 1.0)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_MTOK", 0.0)
    monkeypatch.setattr(settings, "DAILY_COST_LIMIT", 0.5)
    tracker = CostTracker(db_session)
    await tracker.track(response=_response(), task_id=uuid.uuid4())

    outcome = await run_cost_monitor(session=db_session)

    assert Decimal(outcome["total_cost"]) >= Decimal("1.0")
    assert outcome["ratio"] >= 2.0
    assert outcome["level"] in {"degraded", "stopped"}
    assert outcome["alert"] is True


async def test_cost_monitor_normal_usage(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_MTOK", 0.1)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_MTOK", 0.0)
    monkeypatch.setattr(settings, "DAILY_COST_LIMIT", 100.0)
    tracker = CostTracker(db_session)
    await tracker.track(response=_response(tokens=1000), task_id=uuid.uuid4())

    outcome = await run_cost_monitor(session=db_session)

    assert outcome["level"] == "normal"
    assert outcome["alert"] is False


async def test_monitor_task_and_schedule_registered() -> None:
    import app.tasks  # noqa: F401 - 触发任务注册
    from app.core.celery import celery_app

    assert "tasks.monitor_cost" in celery_app.tasks
    assert "daily-cost-monitor" in celery_app.conf.beat_schedule
