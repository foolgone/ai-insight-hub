"""重试执行器（B-307；07-Agent错误重试机制 §3）。

- 单次尝试超时由 ``RetryConfig.timeout`` 控制（``asyncio.wait_for``）；
- 只重试 ``is_retryable`` 判定为可重试的异常，次数上限 ``max_retries``（总尝试 ≤ max_retries+1）；
- 累计耗时超过 ``total_timeout`` 时不再重试；
- 可选 ``CostAwareRetryGuard`` 限制重试消耗的额外 token。
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.retry_config import RetryConfig, is_retryable
from app.utils.retry_guard import CostAwareRetryGuard

T = TypeVar("T")
RetryCallback = Callable[[int, BaseException, float], None]


async def async_retry(
    func: Callable[[int], Awaitable[T]],
    *,
    config: RetryConfig,
    on_retry: RetryCallback | None = None,
    guard: CostAwareRetryGuard | None = None,
) -> T:
    """执行 ``func(attempt)``，按策略重试并返回结果。"""
    started = time.monotonic()
    last_error: BaseException | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await asyncio.wait_for(func(attempt), timeout=config.timeout)
        except Exception as exc:  # noqa: BLE001 - 统一按策略判定
            last_error = exc
            if not is_retryable(exc) or attempt >= config.max_retries:
                raise

            delay = config.delay_for(attempt)
            elapsed = time.monotonic() - started
            if elapsed + delay > config.total_timeout:
                raise

            if guard is not None:
                guard.before_retry(exc)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            await asyncio.sleep(delay)

    # 理论上不可达（循环最后一轮必然 raise 或 return）
    raise last_error if last_error is not None else RuntimeError("retry failed")


__all__ = ["RetryCallback", "async_retry"]
