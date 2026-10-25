"""B-310 BaseAgent 契约测试（成功/输入校验/重试/结构化修复/降级）。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pydantic import BaseModel

from app.agents.base import (
    AgentConfig,
    AgentDegradedError,
    AgentExecutionError,
    AgentInputError,
    BaseAgent,
)
from app.core.config import settings
from app.core.degradation import DegradationLevel
from app.core.degradation_manager import DegradationManager
from app.core.llm import LLMQuotaError, LLMResponse, LLMTimeoutError, LLMUsage

pytestmark = pytest.mark.unit


class _Payload(BaseModel):
    answer: str


class _FakeLLM:
    """按脚本返回内容或抛异常；无脚本时返回空 JSON。"""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, messages, **kwargs) -> LLMResponse:  # noqa: ANN001
        self.calls.append(kwargs)
        item = self._script.pop(0) if self._script else '{"answer": "default"}'
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, tuple):
            content, tokens = item
        else:
            content, tokens = item, (10, 5)
        return LLMResponse(
            content=content,
            usage=LLMUsage(input_tokens=tokens[0], output_tokens=tokens[1]),
            model="fake-model",
            latency_ms=10.0,
        )


class _DummyAgent(BaseAgent):
    output_schema = _Payload

    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        return "你是测试 Agent"

    def _create_agent(self, input_data: Mapping[str, Any]) -> Sequence[Any]:
        return [
            {"role": "system", "content": self._load_prompt()},
            {"role": "user", "content": str(input_data.get("text", ""))},
        ]

    def _validate_input(self, input_data: Mapping[str, Any]) -> None:
        if not input_data.get("text"):
            raise AgentInputError("text is required")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        if isinstance(data, BaseModel):
            return data.model_dump()
        return dict(data)


def _agent(llm: _FakeLLM, **config_kwargs: Any) -> _DummyAgent:
    kwargs: dict[str, Any] = {"max_retries": 2, "retry_base_delay": 0.0}
    kwargs.update(config_kwargs)
    config = AgentConfig(name="dummy_agent", **kwargs)
    return _DummyAgent(config, llm=llm)


def _force_level(monkeypatch, level: DegradationLevel) -> None:
    async def _fake(self, *, user_id=None):  # noqa: ANN001
        return level

    monkeypatch.setattr(DegradationManager, "get_level", _fake)


async def test_invoke_success() -> None:
    llm = _FakeLLM(['{"answer": "hello"}'])
    agent = _agent(llm)

    result = await agent.invoke({"text": "hi"})

    assert result.success is True
    assert result.data == {"answer": "hello"}
    assert result.metadata["agent"] == "dummy_agent"
    assert result.metadata["attempts"] == 1
    assert result.token_usage == {"input": 10, "output": 5}
    assert result.duration >= 0
    assert result.errors == []


async def test_invoke_returns_failure_for_invalid_input() -> None:
    llm = _FakeLLM([])
    agent = _agent(llm)

    result = await agent.invoke({})

    assert result.success is False
    assert any("AgentInputError" in item for item in result.errors)
    assert llm.calls == []


async def test_invoke_retries_retryable_error() -> None:
    llm = _FakeLLM([LLMTimeoutError("timeout"), '{"answer": "ok"}'])
    agent = _agent(llm, max_retries=2)

    result = await agent.invoke({"text": "hi"})

    assert result.success is True
    assert result.metadata["attempts"] == 2
    assert len(llm.calls) == 2


async def test_invoke_does_not_retry_permanent_error() -> None:
    llm = _FakeLLM([LLMQuotaError("quota")])
    agent = _agent(llm)

    result = await agent.invoke({"text": "hi"})

    assert result.success is False
    assert any("LLMQuotaError" in item for item in result.errors)
    assert len(llm.calls) == 1


async def test_invoke_repairs_structured_output() -> None:
    llm = _FakeLLM(["not json", '{"answer": "fixed"}'])
    agent = _agent(llm)

    result = await agent.invoke({"text": "hi"})

    assert result.success is True
    assert result.data == {"answer": "fixed"}
    assert len(llm.calls) == 2
    assert result.token_usage == {"input": 20, "output": 10}


async def test_invoke_fails_when_structured_output_unrepaired() -> None:
    llm = _FakeLLM(["still bad", "still bad after repair"])
    agent = _agent(llm)

    result = await agent.invoke({"text": "hi"})

    assert result.success is False
    assert any("StructuredOutputError" in item for item in result.errors)


async def test_stopped_degradation_rejects_invocation(monkeypatch) -> None:
    _force_level(monkeypatch, DegradationLevel.STOPPED)
    llm = _FakeLLM(['{"answer": "should-not-run"}'])
    agent = _agent(llm)

    result = await agent.invoke({"text": "hi"})

    assert result.success is False
    assert any("AgentDegradedError" in item for item in result.errors)
    assert llm.calls == []


async def test_degraded_level_keeps_main_model_when_unconfigured(monkeypatch) -> None:
    _force_level(monkeypatch, DegradationLevel.DEGRADED)
    monkeypatch.setattr(settings, "DEGRADED_LLM_MODEL", "")
    llm = _FakeLLM(['{"answer": "ok"}'])
    agent = _agent(llm)

    result = await agent.invoke({"text": "hi"})

    assert result.success is True
    assert result.metadata["degradation"] == "degraded"
    assert llm.calls[0]["model"] == settings.DEFAULT_LLM_MODEL


def test_agent_error_tree_flags() -> None:
    assert AgentExecutionError().retryable is True
    assert AgentDegradedError().retryable is False
    assert AgentInputError().retryable is False
