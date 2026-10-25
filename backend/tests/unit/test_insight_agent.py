"""B-601 / B-602 洞察 Agent 与 Prompt 资产测试。"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from app.agents.base import AgentConfig
from app.agents.insight_agent import PROMPT_DIR, InsightAnalysisAgent
from app.core.llm import LLMResponse, LLMUsage

pytestmark = pytest.mark.unit


def _valid_output(**overrides: Any) -> str:
    payload = {
        "intent_distribution": {"咨询": 6, "投诉": 2, "建议": 2},
        "top_questions": [{"question": "退货政策", "count": 3, "ratio": 0.3}],
        "sentiment_distribution": {"正面": 0.4, "中性": 0.5, "负面": 0.1},
        "sentiment_trend": [
            {"date": "2025-01-15", "positive": 0.4, "neutral": 0.5, "negative": 0.1}
        ],
        "pain_points": [
            {
                "issue": "退货流程复杂",
                "frequency": 3,
                "severity": "high",
                "suggestions": "简化流程",
            }
        ],
        "unresolved_issues": [{"question": "能否开发票", "count": 1, "reason": "未回答"}],
        "emerging_topics": ["新产品咨询增加 30%"],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


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
            usage=LLMUsage(input_tokens=300, output_tokens=150),
            model="fake-model",
            latency_ms=10.0,
        )


def _agent(llm: _FakeLLM) -> InsightAnalysisAgent:
    return InsightAnalysisAgent(
        AgentConfig(name="insight_agent", max_retries=0, retry_base_delay=0.0),
        llm=llm,
    )


def _input(
    dialogues: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "datasource_id": str(uuid.uuid4()),
        "dialogues": dialogues
        if dialogues is not None
        else [
            {
                "dialogue_id": "1",
                "timestamp": "2025-01-15T10:30:00",
                "user_message": "怎么退货",
                "ai_response": "在订单页申请",
            }
        ],
        "config": config or {},
    }


def test_prompt_assets() -> None:
    assert (PROMPT_DIR / "system.txt").is_file()
    assert (PROMPT_DIR / "version.txt").is_file()
    examples = json.loads((PROMPT_DIR / "examples.json").read_text(encoding="utf-8"))
    assert examples
    tasks = {path.stem for path in (PROMPT_DIR / "tasks").glob("*.txt")}
    assert tasks == {
        "intent_classification",
        "sentiment_analysis",
        "pain_point_detection",
        "trend_analysis",
    }


def test_default_config_matches_design() -> None:
    agent = InsightAnalysisAgent(llm=_FakeLLM([]))

    assert agent.config.temperature == 0.3
    assert agent.config.timeout == 120


async def test_analyze_success() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.analyze(_input())

    assert result.success is True
    data = result.data or {}
    assert data["intent_distribution"] == {"咨询": 6, "投诉": 2, "建议": 2}
    assert data["top_questions"][0]["count"] == 3
    assert data["degraded"] is False
    assert data["statistics"]["sentiment_sum"] == 1.0
    assert data["pain_points"][0]["issue"] == "退货流程复杂"


async def test_sentiment_normalization() -> None:
    llm = _FakeLLM([_valid_output(sentiment_distribution={"正面": 2.0, "中性": 2.0, "负面": 1.0})])
    agent = _agent(llm)

    result = await agent.analyze(_input())

    sentiment = (result.data or {})["sentiment_distribution"]
    assert sentiment == {"正面": 0.4, "中性": 0.4, "负面": 0.2}
    assert round(sum(sentiment.values()), 4) == 1.0


async def test_sentiment_failure_degrades() -> None:
    llm = _FakeLLM([_valid_output(sentiment_distribution={"正面": 0, "中性": 0, "负面": 0})])
    agent = _agent(llm)

    result = await agent.analyze(_input())

    data = result.data or {}
    assert result.success is True
    assert data["sentiment_distribution"] == {}
    assert data["degraded"] is True


async def test_sentiment_disabled_is_not_degraded() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.analyze(_input(config={"analyze_sentiment": False}))

    data = result.data or {}
    assert data["sentiment_distribution"] == {}
    assert data["degraded"] is False


async def test_trends_and_pain_points_switches() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.analyze(
        _input(config={"identify_trends": False, "find_pain_points": False})
    )

    data = result.data or {}
    assert data["sentiment_trend"] == []
    assert data["pain_points"] == []


async def test_invalid_input() -> None:
    llm = _FakeLLM([])
    agent = _agent(llm)

    result = await agent.analyze(_input(dialogues=[]))

    assert result.success is False
    assert any("AgentInputError" in item for item in result.errors)
    assert llm.calls == []


async def test_repairs_invalid_json() -> None:
    llm = _FakeLLM(["not json", _valid_output()])
    agent = _agent(llm)

    result = await agent.analyze(_input())

    assert result.success is True
    assert len(llm.calls) == 2
