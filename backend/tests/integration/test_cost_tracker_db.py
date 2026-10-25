"""B-306 成本追踪数据库测试（llm_calls 幂等 / 失败回写 / 日成本 / 用量统计）。"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.cost_tracker import CostTracker
from app.core.llm import LLMResponse, LLMUsage
from app.models import LlmCall
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration


def _response(
    *, model: str = "deepseek-flash", tokens: tuple[int, int] = (100, 50), latency_ms: float = 120.0
) -> LLMResponse:
    return LLMResponse(
        content="ok",
        usage=LLMUsage(input_tokens=tokens[0], output_tokens=tokens[1]),
        model=model,
        latency_ms=latency_ms,
    )


async def test_track_writes_success_row(db_session) -> None:
    tracker = CostTracker(db_session)
    task_id = uuid.uuid4()

    row = await tracker.track(
        response=_response(),
        task_id=task_id,
        attempt=0,
        agent_name="cleaning_agent",
        agent_version="v1.0.0",
    )

    assert row.status == "success"
    assert row.idempotency_key == f"{task_id}:0"
    assert row.total_tokens == 150
    assert row.agent_name == "cleaning_agent"

    stored = (
        await db_session.execute(select(LlmCall).where(LlmCall.idempotency_key == f"{task_id}:0"))
    ).scalar_one()
    assert stored.total_tokens == 150
    assert stored.duration == pytest.approx(0.12)


async def test_track_is_idempotent_for_same_attempt(db_session) -> None:
    tracker = CostTracker(db_session)
    task_id = uuid.uuid4()

    await tracker.track(response=_response(tokens=(100, 50)), task_id=task_id, attempt=0)
    await tracker.track(response=_response(tokens=(200, 100)), task_id=task_id, attempt=0)

    count = await db_session.scalar(
        select(func.count()).select_from(LlmCall).where(LlmCall.task_id == task_id)
    )
    assert count == 1
    row = (await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id))).scalar_one()
    assert row.total_tokens == 300


async def test_failure_writes_back_same_row(db_session) -> None:
    tracker = CostTracker(db_session)
    task_id = uuid.uuid4()
    await tracker.track(response=_response(), task_id=task_id, attempt=2)

    row = await tracker.record_failure(
        error=RuntimeError("provider boom"),
        model="deepseek-flash",
        task_id=task_id,
        attempt=2,
    )

    assert row.status == "failed"
    assert row.error_type == "RuntimeError"
    assert "provider boom" in (row.error_message or "")
    assert row.total_tokens == 0

    stored = (
        await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id))
    ).scalar_one()
    assert stored.status == "failed"
    assert stored.total_tokens == 0


async def test_daily_cost_and_usage_stats(db_session, monkeypatch) -> None:
    # 固定单价，避免 D-09 的 0.0 导致成本恒 0
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_MTOK", 1.0)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_MTOK", 2.0)
    user = UserFactory()
    await persist(db_session, user)
    tracker = CostTracker(db_session)
    task_one = uuid.uuid4()
    task_two = uuid.uuid4()

    # 加 user_id 过滤：本地/共享库可能已有其它 llm_calls 记录，避免全局聚合受污染
    await tracker.track(
        response=_response(tokens=(1_000_000, 0)),
        task_id=task_one,
        user_id=user.id,
    )
    await tracker.track(
        response=_response(model="deepseek-flash", tokens=(0, 500_000)),
        task_id=task_two,
        attempt=1,
        user_id=user.id,
    )

    daily = await tracker.get_daily_cost(user_id=user.id)
    assert daily == Decimal("2.00000000")

    stats = await tracker.get_usage_stats(days=7, user_id=user.id)
    assert stats["calls"] == 2
    assert stats["total_tokens"] == 1_500_000
    assert stats["total_cost"] == "2.00000000"
    assert "deepseek-flash" in stats["by_model"]


async def test_usage_stats_with_user_filter(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    tracker = CostTracker(db_session)
    await tracker.track(response=_response(), task_id=uuid.uuid4(), user_id=user.id)

    stats = await tracker.get_usage_stats(user_id=user.id)
    assert stats["calls"] == 1
