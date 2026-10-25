"""B-307 重试机制与成本守卫单测。"""
from __future__ import annotations

import asyncio
import random

import pytest

from app.core.llm import LLMQuotaError, LLMTimeoutError
from app.core.retry_config import RetryConfig, is_retryable
from app.utils.retry import async_retry
from app.utils.retry_guard import CostAwareRetryGuard, CostLimitExceededError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (LLMTimeoutError("t"), True),
        (TimeoutError("t"), True),
        (ConnectionError("c"), False),
        (ValueError("v"), False),
        (LLMQuotaError("q"), False),
    ],
)
def test_is_retryable_classification(exc: BaseException, expected: bool) -> None:
    assert is_retryable(exc) is expected


def test_delay_backoff_without_jitter() -> None:
    config = RetryConfig(initial_delay=1.0, backoff_factor=2.0, max_delay=5.0, jitter=False)

    assert [config.delay_for(i) for i in range(4)] == [1.0, 2.0, 4.0, 5.0]


def test_delay_with_jitter_stays_in_bounds() -> None:
    config = RetryConfig(initial_delay=2.0, jitter=True)

    delay = config.delay_for(0, rng=random.Random(42))

    assert 1.0 <= delay <= 3.0


async def test_retries_then_succeeds() -> None:
    calls: list[int] = []
    retries: list[tuple[int, float]] = []

    async def func(attempt: int) -> str:
        calls.append(attempt)
        if attempt < 2:
            raise LLMTimeoutError("first attempts fail")
        return "ok"

    result = await async_retry(
        func,
        config=RetryConfig(max_retries=3, initial_delay=0.0),
        on_retry=lambda attempt, exc, delay: retries.append((attempt, delay)),
    )

    assert result == "ok"
    assert calls == [0, 1, 2]
    assert [item[0] for item in retries] == [0, 1]


async def test_non_retryable_raises_immediately() -> None:
    calls: list[int] = []

    async def func(attempt: int) -> str:
        calls.append(attempt)
        raise LLMQuotaError("quota exhausted")

    with pytest.raises(LLMQuotaError):
        await async_retry(func, config=RetryConfig(initial_delay=0.0))

    assert calls == [0]


async def test_exhausts_retry_budget() -> None:
    calls: list[int] = []

    async def func(attempt: int) -> str:
        calls.append(attempt)
        raise LLMTimeoutError("always timeout")

    with pytest.raises(LLMTimeoutError):
        await async_retry(func, config=RetryConfig(max_retries=2, initial_delay=0.0))

    assert calls == [0, 1, 2]


async def test_per_attempt_timeout_is_retryable() -> None:
    calls: list[int] = []

    async def func(attempt: int) -> str:
        calls.append(attempt)
        await asyncio.sleep(0.05)
        return "late"

    with pytest.raises(TimeoutError):
        await async_retry(
            func,
            config=RetryConfig(max_retries=1, initial_delay=0.0, timeout=0.01),
        )

    assert len(calls) == 2


async def test_guard_blocks_retry_when_token_budget_exceeded() -> None:
    async def func(attempt: int) -> str:
        error = LLMTimeoutError("timeout with usage")
        error.total_tokens = 5000  # type: ignore[attr-defined]
        raise error

    guard = CostAwareRetryGuard(max_extra_tokens=4000)

    with pytest.raises(CostLimitExceededError):
        await async_retry(func, config=RetryConfig(initial_delay=0.0), guard=guard)

    assert guard.used_tokens == 5000


async def test_guard_reset() -> None:
    guard = CostAwareRetryGuard(max_extra_tokens=10)
    error = LLMTimeoutError("x")
    error.total_tokens = 5  # type: ignore[attr-defined]
    guard.before_retry(error)

    guard.reset()

    assert guard.used_tokens == 0
