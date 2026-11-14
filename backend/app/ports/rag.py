"""RAG 端口：评测平台只依赖「执行一次检索/问答并拿到标准化结果」这一件事。

实现（WeKnora / Mock）放在 ``app/services/rag``，由构造参数注入，
业务 service 不 import 具体实现（与 ``LLMPort`` / ``CredentialPort`` 同构）。

两种模式必须区分（Phase 2 决策 Q2）：
- ``retrieve``：只调检索接口（hybrid-search），产出 ``context_source="hybrid_search"``；
- ``query``：调端到端问答（agent-chat），产出 ``context_source="agent_chat"``。
  **不得**把独立检索的结果当作生成时使用的上下文——若外部未返回上下文，
  ``context_source="none"`` 且 ``missing`` 标注 ``retrieved_contexts``，
  Phase 3 的 Faithfulness 必须据此 skip，而不是借用另一条链路。
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

RAGMode = Literal["retrieve", "query"]
ContextSource = Literal["hybrid_search", "agent_chat", "none"]


@dataclass(frozen=True)
class RetrievedContext:
    """一条检索片段（对外统一结构，屏蔽外部字段差异）。"""

    content: str
    document_id: str | None = None
    chunk_id: str | None = None
    title: str | None = None
    score: float | None = None
    rank: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RAGResult:
    """一次 RAG 执行的标准化结果。

    ``missing`` 记录外部系统未提供的字段（如 ``token_usage`` / ``score``），
    用于区分「没有这个值」与「值是 0」。
    """

    query: str
    mode: RAGMode
    contexts: tuple[RetrievedContext, ...]
    latency_ms: int
    context_source: ContextSource = "none"
    answer: str | None = None
    external_session_id: str | None = None
    model_config: Mapping[str, Any] = field(default_factory=dict)
    retrieval_config: Mapping[str, Any] = field(default_factory=dict)
    prompt_snapshot: Mapping[str, Any] = field(default_factory=dict)
    token_usage: Mapping[str, Any] | None = None
    raw: Mapping[str, Any] | str | None = None
    missing: tuple[str, ...] = ()


@runtime_checkable
class RAGPort(Protocol):
    """外部 RAG 适配器接口。"""

    name: str

    async def query(self, query: str, *, config: Mapping[str, Any] | None = None) -> RAGResult:
        """端到端问答（返回答案 + 生成时真实使用的上下文，若有）。"""
        ...

    async def retrieve(self, query: str, *, config: Mapping[str, Any] | None = None) -> RAGResult:
        """纯检索（只返回片段，不生成答案）。"""
        ...

    async def health_check(self) -> bool:
        """探测外部服务是否可用（不抛异常）。"""
        ...

    async def aclose(self) -> None:
        ...


__all__ = [
    "ContextSource",
    "RAGMode",
    "RAGPort",
    "RAGResult",
    "RetrievedContext",
]
