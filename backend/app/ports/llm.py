"""LLM 端口：业务代码只需要「能发消息、拿回内容」这一件事。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from app.core.llm import LLMResponse, Message


@runtime_checkable
class LLMPort(Protocol):
    """LLM 调用接口（非流式）。

    与 ``app.core.llm.LLMClient`` 保持结构一致：实现类无需继承本协议，
    只要方法签名匹配即可被注入。
    """

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        ...

    async def aclose(self) -> None:
        ...


__all__ = ["LLMPort"]
