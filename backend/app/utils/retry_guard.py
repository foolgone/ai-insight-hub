"""成本感知的重试守卫（B-307；07-Agent错误重试机制 §4.3）。

重试会带来额外 token 消耗；累计超过预算时抛 ``CostLimitExceededError`` 终止重试
（该异常本身不可重试）。
"""
from __future__ import annotations


class CostLimitExceededError(Exception):
    """重试额外 token 超预算。"""

    retryable = False


class CostAwareRetryGuard:
    """累计重试 token，超预算即终止。"""

    def __init__(self, max_extra_tokens: int = 20_000) -> None:
        self.max_extra_tokens = max_extra_tokens
        self._used_tokens = 0

    @property
    def used_tokens(self) -> int:
        return self._used_tokens

    def before_retry(self, exc: BaseException) -> None:
        """记录本次失败消耗的 token；超预算抛 ``CostLimitExceededError``。"""
        raw = getattr(exc, "total_tokens", 0) or 0
        try:
            tokens = int(raw)
        except (TypeError, ValueError):
            tokens = 0
        self._used_tokens += max(0, tokens)

        if self._used_tokens > self.max_extra_tokens:
            raise CostLimitExceededError(
                "retry token budget exceeded: " f"{self._used_tokens} > {self.max_extra_tokens}"
            )

    def reset(self) -> None:
        self._used_tokens = 0


__all__ = ["CostAwareRetryGuard", "CostLimitExceededError"]
