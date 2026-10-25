"""B-312 / B-313 清洗 Prompt 资产与 DataCleaningAgent 测试。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.agents.base import AgentConfig
from app.agents.cleaning_agent import (
    PROMPT_DIR,
    STATE_SEQUENCE,
    DataCleaningAgent,
)
from app.core.llm import LLMResponse, LLMUsage
from app.schemas.agents.cleaning import CleaningState

pytestmark = pytest.mark.unit

_DATASOURCE_ID = "00000000-0000-0000-0000-000000000001"


def _valid_output(dialogues: list[dict[str, Any]] | None = None) -> str:
    items = dialogues or [
        {
            "dialogue_id": "1",
            "timestamp": "2025-01-15T10:30:00",
            "user_message": "iPhone 14 多少钱",
            "ai_response": "5999 元起",
            "quality_score": 95,
            "issues": [],
        },
        {
            "dialogue_id": "2",
            "timestamp": None,
            "user_message": "可以分期吗",
            "ai_response": "支持花呗 12 期",
            "quality_score": 85,
            "issues": ["missing_timestamp"],
        },
    ]
    return json.dumps(
        {
            "datasource_id": _DATASOURCE_ID,
            "dialogues": items,
            "statistics": {},
        },
        ensure_ascii=False,
    )


class _FakeLLM:
    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[Any] = []

    async def chat(self, messages, **kwargs) -> LLMResponse:  # noqa: ANN001
        self.calls.append(messages)
        item = self._script.pop(0) if self._script else _valid_output()
        if isinstance(item, BaseException):
            raise item
        return LLMResponse(
            content=item,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="fake-model",
            latency_ms=10.0,
        )


def _agent(llm: _FakeLLM) -> DataCleaningAgent:
    return DataCleaningAgent(
        AgentConfig(name="cleaning_agent", max_retries=0, retry_base_delay=0.0),
        llm=llm,
    )


def _input(raw_data: str = "客户：你好 客服：您好", **overrides: Any) -> dict:
    payload = {
        "datasource_id": str(uuid.uuid4()),
        "raw_data": raw_data,
        "data_type": "txt",
    }
    payload.update(overrides)
    return payload


def test_prompt_assets_are_valid() -> None:
    system = (PROMPT_DIR / "system.txt").read_text(encoding="utf-8")
    examples = json.loads((PROMPT_DIR / "examples.json").read_text(encoding="utf-8"))
    version = (PROMPT_DIR / "version.txt").read_text(encoding="utf-8")

    assert "JSON" in system and "dialogues" in system
    assert len(examples) >= 10
    for example in examples:
        assert "input" in example and "output" in example
        assert example["output"]["dialogues"]
    assert version.strip().startswith("v")


def test_state_machine_has_six_states() -> None:
    assert len(STATE_SEQUENCE) == 6
    assert STATE_SEQUENCE[0] is CleaningState.PENDING
    assert STATE_SEQUENCE[-1] is CleaningState.COMPLETED


def test_tools_registered() -> None:
    agent = _agent(_FakeLLM([]))

    assert set(agent.tools) == {
        "parse_csv",
        "parse_json",
        "detect_duplicates",
        "normalize_text",
        "extract_timestamp",
    }


def test_create_agent_includes_few_shot_and_normalized_text() -> None:
    agent = _agent(_FakeLLM([]))

    messages = agent._create_agent(_input(raw_data="  你好\u200b   世界  "))

    assert messages[0]["role"] == "system"
    assert len(messages) >= 4  # system + few-shot + user
    assert "你好 世界" in messages[-1]["content"]


def test_long_input_is_accepted() -> None:
    agent = _agent(_FakeLLM([]))
    long_text = "客户：你好，请问什么时候发货？ 客服：48 小时内。\n" * 2000

    messages = agent._create_agent(_input(raw_data=long_text))

    assert len(messages[-1]["content"]) > 50_000


async def test_clean_success_recomputes_counts() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.clean(_input())

    assert result.success is True
    data = result.data or {}
    assert data["datasource_id"] == _DATASOURCE_ID
    assert data["cleaned_records"] == 2
    assert data["total_records"] == 2
    assert data["failed_records"] == 0
    assert data["statistics"]["avg_quality_score"] == 90.0
    assert result.metadata["agent"] == "cleaning_agent"


async def test_clean_invalid_input_returns_failure() -> None:
    llm = _FakeLLM([])
    agent = _agent(llm)

    result = await agent.clean({"raw_data": "", "data_type": "txt"})

    assert result.success is False
    assert any("AgentInputError" in item for item in result.errors)
    assert llm.calls == []


async def test_clean_repairs_invalid_json_once() -> None:
    llm = _FakeLLM(["not json", _valid_output()])
    agent = _agent(llm)

    result = await agent.clean(_input())

    assert result.success is True
    assert len(llm.calls) == 2


async def test_clean_fails_after_repair_failure() -> None:
    llm = _FakeLLM(["bad", "still bad"])
    agent = _agent(llm)

    result = await agent.clean(_input())

    assert result.success is False
    assert any("StructuredOutputError" in item for item in result.errors)


async def test_clean_rejects_empty_dialogues() -> None:
    empty = json.dumps({"datasource_id": _DATASOURCE_ID, "dialogues": [], "statistics": {}})
    llm = _FakeLLM([empty])
    agent = _agent(llm)

    result = await agent.clean(_input())

    assert result.success is False
    assert any("AgentOutputError" in item for item in result.errors)


def test_prompt_dir_exists() -> None:
    assert (Path(PROMPT_DIR) / "system.txt").is_file()
