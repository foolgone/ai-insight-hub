"""B-401 / B-402 质量评估 Agent 与 Prompt 资产测试。"""
from __future__ import annotations

import json
from typing import Any

import pytest

from app.agents.base import AgentConfig
from app.agents.evaluation_agent import (
    PROMPT_DIR,
    QualityEvaluationAgent,
    compute_overall_score,
    quality_level_for,
)
from app.core.llm import LLMResponse, LLMUsage

pytestmark = pytest.mark.unit

_KB = [{"question": "iPhone 14 多少钱", "answer": "5999 元起"}]


def _dimensions(
    accuracy: float = 90,
    completeness: float = 80,
    hallucination: float = 82,
    tone: float = 88,
    compliance: float = 95,
    issues: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    issues = issues or {}
    return {
        "accuracy": {"score": accuracy, "issues": issues.get("accuracy", [])},
        "completeness": {
            "score": completeness,
            "issues": issues.get("completeness", []),
        },
        "hallucination": {
            "score": hallucination,
            "issues": issues.get("hallucination", []),
        },
        "tone": {"score": tone, "issues": issues.get("tone", [])},
        "compliance": {
            "score": compliance,
            "issues": issues.get("compliance", []),
        },
    }


def _valid_output(**overrides: Any) -> str:
    payload = {
        "dimensions": _dimensions(**overrides),
        "suggestions": ["可以补充售后说明"],
    }
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
            usage=LLMUsage(input_tokens=100, output_tokens=50),
            model="fake-model",
            latency_ms=10.0,
        )


def _agent(llm: _FakeLLM) -> QualityEvaluationAgent:
    return QualityEvaluationAgent(
        AgentConfig(name="evaluation_agent", max_retries=0, retry_base_delay=0.0),
        llm=llm,
    )


def _input(
    knowledge_base: list[dict[str, Any]] | None = None,
    dimensions: list[str] | None = None,
    threshold: float = 70,
) -> dict[str, Any]:
    config: dict[str, Any] = {"threshold": threshold}
    if dimensions is not None:
        config["dimensions"] = dimensions
    return {
        "dialogue": {
            "dialogue_id": "d-1",
            "user_message": "iPhone 14 多少钱",
            "ai_response": "5999 元起",
        },
        "knowledge_base": knowledge_base if knowledge_base is not None else _KB,
        "config": config,
    }


def test_compute_overall_full_dimensions() -> None:
    scores = {
        "accuracy": 90,
        "completeness": 80,
        "hallucination": 82,
        "tone": 88,
        "compliance": 95,
    }
    overall = compute_overall_score(scores, list(scores))

    assert overall == 86.2


def test_compute_overall_subset_normalizes_weights() -> None:
    scores = {"accuracy": 90, "completeness": 80, "tone": 88}
    overall = compute_overall_score(scores, list(scores))

    assert overall == 86.1


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (100, "excellent"),
        (90, "excellent"),
        (89.9, "good"),
        (75, "good"),
        (74.9, "fair"),
        (60, "fair"),
        (59.9, "poor"),
        (0, "poor"),
    ],
)
def test_quality_level_boundaries(score: float, level: str) -> None:
    assert quality_level_for(score).value == level


def test_prompt_assets_exist() -> None:
    assert (PROMPT_DIR / "system.txt").is_file()
    assert (PROMPT_DIR / "version.txt").is_file()
    dimension_dir = PROMPT_DIR / "dimensions"
    files = {path.stem for path in dimension_dir.glob("*.txt")}
    assert files == {
        "accuracy",
        "completeness",
        "hallucination",
        "tone",
        "compliance",
    }
    version = (PROMPT_DIR / "version.txt").read_text(encoding="utf-8")
    assert version.strip().startswith("v")


def test_loaded_prompt_contains_dimension_definitions() -> None:
    agent = _agent(_FakeLLM([]))

    prompt = agent._load_prompt()

    assert "准确性" in prompt
    assert "合规性" in prompt
    assert "hallucination" in prompt


async def test_evaluate_success_with_knowledge_base() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.evaluate(_input())

    assert result.success is True
    data = result.data or {}
    assert data["dialogue_id"] == "d-1"
    assert data["overall_score"] == 86.2
    assert data["needs_review"] is False
    assert data["quality_level"] == "good"
    assert data["has_issues"] is False
    assert set(data["dimensions"]) == {
        "accuracy",
        "completeness",
        "hallucination",
        "tone",
        "compliance",
    }


async def test_evaluate_empty_knowledge_forces_hallucination_70() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.evaluate(_input(knowledge_base=[]))

    data = result.data or {}
    assert data["dimensions"]["hallucination"]["score"] == 70.0
    assert "knowledge_base_empty" in data["dimensions"]["hallucination"]["issues"]
    assert data["overall_score"] == 83.8
    assert any("知识库为空" in item for item in data["suggestions"])


async def test_evaluate_low_scores_needs_review() -> None:
    llm = _FakeLLM(
        [
            _valid_output(
                accuracy=50,
                completeness=55,
                hallucination=50,
                tone=60,
                compliance=50,
            )
        ]
    )
    agent = _agent(llm)

    result = await agent.evaluate(_input())

    data = result.data or {}
    assert data["overall_score"] == 52.2
    assert data["needs_review"] is True
    assert data["quality_level"] == "poor"
    assert data["critical_issues"]
    assert data["has_issues"] is True


async def test_evaluate_with_subset_dimensions() -> None:
    subset_output = json.dumps(
        {
            "dimensions": {
                "accuracy": {"score": 90, "issues": []},
                "completeness": {"score": 80, "issues": []},
                "tone": {"score": 88, "issues": []},
            },
            "suggestions": [],
        },
        ensure_ascii=False,
    )
    llm = _FakeLLM([subset_output])
    agent = _agent(llm)

    result = await agent.evaluate(
        _input(dimensions=["accuracy", "completeness", "tone"], threshold=80)
    )

    data = result.data or {}
    assert data["overall_score"] == 86.1
    assert set(data["dimensions"]) == {"accuracy", "completeness", "tone"}
    assert data["needs_review"] is False


async def test_evaluate_missing_dimension_fails() -> None:
    partial = json.dumps(
        {"dimensions": {"accuracy": {"score": 80, "issues": []}}, "suggestions": []}
    )
    llm = _FakeLLM([partial])
    agent = _agent(llm)

    result = await agent.evaluate(_input())

    assert result.success is False
    assert any("AgentOutputError" in item for item in result.errors)


async def test_evaluate_invalid_input_fails() -> None:
    llm = _FakeLLM([])
    agent = _agent(llm)

    result = await agent.evaluate(
        {"dialogue": {"dialogue_id": "d", "user_message": "", "ai_response": ""}}
    )

    assert result.success is False
    assert any("AgentInputError" in item for item in result.errors)
    assert llm.calls == []


async def test_evaluate_repairs_invalid_json() -> None:
    llm = _FakeLLM(["not json", _valid_output()])
    agent = _agent(llm)

    result = await agent.evaluate(_input())

    assert result.success is True
    assert len(llm.calls) == 2
