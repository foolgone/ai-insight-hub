"""B-310 BaseAgent 成本/失败落库集成测试（llm_calls）。"""
from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.base import AgentConfig, BaseAgent
from app.core.llm import LLMQuotaError, LLMResponse, LLMUsage
from app.models import LlmCall

pytestmark = pytest.mark.integration


class _Payload(BaseModel):
    answer: str


class _FakeLLM:
    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)

    async def chat(self, messages, **kwargs) -> LLMResponse:  # noqa: ANN001
        item = self._script.pop(0) if self._script else '{"answer": "default"}'
        if isinstance(item, BaseException):
            raise item
        return LLMResponse(
            content=item,
            usage=LLMUsage(input_tokens=20, output_tokens=10),
            model="fake-model",
            latency_ms=15.0,
        )


class _Agent(BaseAgent):
    output_schema = _Payload

    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        return "prompt"

    def _create_agent(self, input_data: Mapping[str, Any]) -> Sequence[Any]:
        return [{"role": "user", "content": str(input_data.get("text", ""))}]

    def _validate_input(self, input_data: Mapping[str, Any]) -> None:
        if not input_data.get("text"):
            raise ValueError("text is required")

    def _validate_output(self, data: Any) -> dict[str, Any]:
        return data.model_dump() if isinstance(data, BaseModel) else dict(data)


def _agent(llm: _FakeLLM) -> _Agent:
    return _Agent(
        AgentConfig(name="agent-cost-test", max_retries=0, retry_base_delay=0.0),
        llm=llm,
    )


async def test_success_persists_llm_call(db_session) -> None:
    task_id = uuid.uuid4()
    agent = _agent(_FakeLLM(['{"answer": "ok"}']))

    result = await agent.invoke({"text": "hi"}, session=db_session, task_id=task_id)

    assert result.success is True
    row = (await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id))).scalar_one()
    assert row.status == "success"
    assert row.total_tokens == 30
    assert row.agent_name == "agent-cost-test"
    assert row.idempotency_key == f"{task_id}:0"


async def test_failure_persists_failed_llm_call(db_session) -> None:
    task_id = uuid.uuid4()
    agent = _agent(_FakeLLM([LLMQuotaError("quota exhausted")]))

    result = await agent.invoke({"text": "hi"}, session=db_session, task_id=task_id)

    assert result.success is False
    row = (await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id))).scalar_one()
    assert row.status == "failed"
    assert row.error_type == "LLMQuotaError"
    assert row.total_tokens == 0


async def test_no_session_skips_tracking(db_session) -> None:
    task_id = uuid.uuid4()
    agent = _agent(_FakeLLM(['{"answer": "ok"}']))

    result = await agent.invoke({"text": "hi"}, task_id=task_id)

    assert result.success is True
    rows = (
        (await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id)))
        .scalars()
        .all()
    )
    assert rows == []
