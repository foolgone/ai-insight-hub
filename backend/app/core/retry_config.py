"""重试配置与异常分类（B-307；07-Agent错误重试机制 §3）。

- 只重试瞬时错误（连接/超时/限流/过载/5xx），永久错误（认证/参数/上下文/配额）不重试；
- 异常判定优先用 ``retryable`` 属性，其次按类名白/黑名单；
- 退避：``min(initial_delay × factor**attempt, max_delay) × (0.5 + random())``。
"""
from __future__ import annotations

import random
from dataclasses import dataclass

# 可重试异常类名（与 LLMClient / 通用 SDK 命名对齐）
RETRYABLE_EXCEPTION_NAMES: frozenset[str] = frozenset(
    {
        "APIConnectionError",
        "TimeoutError",
        "RateLimitError",
        "ServiceUnavailableError",
        "OverloadedError",
        "LLMConnectionError",
        "LLMTimeoutError",
        "LLMRateLimitError",
        "LLMOverloadedError",
        "LLMServerError",
    }
)

# 永久错误：命中即不重试（即使类名未在可重试名单）
NON_RETRYABLE_EXCEPTION_NAMES: frozenset[str] = frozenset(
    {
        "AuthenticationError",
        "ValidationError",
        "InvalidPromptError",
        "ContextLengthExceededError",
        "QuotaExceededError",
        "LLMAuthenticationError",
        "LLMValidationError",
        "LLMContextLengthError",
        "LLMQuotaError",
        "LLMResponseFormatError",
        "AgentInputError",
        "ParseError",
        "StructuredOutputError",
        "CostLimitExceededError",
    }
)


def is_retryable(exc: BaseException) -> bool:
    """判定异常是否可重试（``retryable`` 属性优先）。"""
    flag = getattr(exc, "retryable", None)
    if isinstance(flag, bool):
        return flag
    name = type(exc).__name__
    if name in NON_RETRYABLE_EXCEPTION_NAMES:
        return False
    return name in RETRYABLE_EXCEPTION_NAMES


@dataclass(frozen=True)
class RetryConfig:
    """重试参数（默认值来自 07 文档 §3.1）。"""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    timeout: float = 60.0
    total_timeout: float = 180.0
    jitter: bool = True
    max_retry_tokens: int = 20_000

    def delay_for(self, attempt: int, rng: random.Random | None = None) -> float:
        """第 ``attempt`` 次重试前的等待秒数（attempt 从 0 开始）。"""
        base = min(self.initial_delay * (self.backoff_factor**attempt), self.max_delay)
        if not self.jitter:
            return base
        generator = rng or random
        return base * (0.5 + generator.random())


__all__ = [
    "NON_RETRYABLE_EXCEPTION_NAMES",
    "RETRYABLE_EXCEPTION_NAMES",
    "RetryConfig",
    "is_retryable",
]
