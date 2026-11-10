"""Agent 基类的资源生命周期测试。

背景：BYOK 场景下每次调用都会临时新建 ``LLMClient``，如果不关闭，
httpx 连接池会随调用累积（长驻 worker 的 FD 泄漏）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.agents import base as agent_base
from app.agents.base import AgentConfig, BaseAgent
from app.core.llm import LLMResponse, LLMUsage

pytestmark = pytest.mark.unit


class _CountingLLM:
    """记录 aclose 调用次数的 fake 客户端。"""

    def __init__(self) -> None:
        self.closed = 0
        self.calls = 0

    async def chat(self, messages, **kwargs: Any) -> LLMResponse:  # noqa: ANN001
        self.calls += 1
        return LLMResponse(
            content="ok",
            usage=LLMUsage(input_tokens=1, output_tokens=1),
            model="fake",
            latency_ms=1.0,
        )

    async def aclose(self) -> None:
        self.closed += 1


class _Agent(BaseAgent):
    def _init_tools(self) -> None:
        self.tools = {}

    def _load_prompt(self) -> str:
        return "system"

    def _validate_input(self, input_data: Any) -> None:  # noqa: ANN401
        return None

    def _create_agent(self, input_data: Any) -> list[dict[str, str]]:  # noqa: ANN401
        return [{"role": "user", "content": "hi"}]

    def _validate_output(self, data: Any) -> dict[str, Any]:  # noqa: ANN401
        return {"ok": True}


class _Session:
    """够用的假 session：成本追踪会写库，这里全部 no-op。"""

    async def scalar(self, *_args: Any, **_kwargs: Any) -> int:
        return 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
        return None

    def add(self, _obj: Any) -> None:  # noqa: ANN401
        return None

    async def flush(self) -> None:
        return None


def test_shared_llm_reuses_client_per_model() -> None:
    """服务端 Key 场景复用进程级客户端，不再每次新建连接池。"""
    first = agent_base._shared_llm("unit-test-model", 5.0)
    second = agent_base._shared_llm("unit-test-model", 5.0)
    assert first is second


@pytest.mark.asyncio
async def test_byok_client_is_closed_after_invoke(monkeypatch) -> None:
    """BYOK 临时客户端在 invoke 结束后必须关闭。"""
    created: list[_CountingLLM] = []

    def _make_client(**kwargs: Any) -> _CountingLLM:  # noqa: ANN401
        client = _CountingLLM()
        created.append(client)
        return client

    class _Credential:
        status = "active"

    class _CredentialService:
        async def get_credential(self, session, user_id):  # noqa: ANN001, ANN202
            return _Credential()

        def decrypt_credential(self, credential):  # noqa: ANN001, ANN202
            return "sk-user"

    monkeypatch.setattr(agent_base, "LLMClient", _make_client)
    monkeypatch.setattr(agent_base.settings, "ALLOW_SERVER_KEY_FALLBACK", False)
    agent_base._LLM_CLIENTS.clear()

    import app.services.credential_service as credential_module

    monkeypatch.setattr(credential_module, "credential_service", _CredentialService())

    agent = _Agent(AgentConfig(name="unit-agent", max_retries=0), llm=None)
    result = await agent.invoke({"q": "hi"}, session=_Session(), user_id=uuid.uuid4())

    assert result.success is True
    # created[0] 是进程级共享客户端（不随单次调用关闭），created[1] 是 BYOK 临时客户端
    assert len(created) == 2
    assert created[0] is agent.llm
    assert created[0].closed == 0
    assert created[1].closed == 1
