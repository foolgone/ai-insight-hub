"""RagJudgeAgent 单测（Phase 3B）：结构解析、修复轮、raw_text、输入校验、版本元信息。

全部使用 Fake LLM，不访问真实 API。
"""
from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentConfig
from app.agents.rag_judge_agent import RagJudgeAgent
from app.core.llm import LLMResponse, LLMUsage

pytestmark = pytest.mark.unit

FAITHFULNESS_JSON = (
    '{"claims": ['
    '{"claim": "退款 1-3 天到账", "supported": true, "evidence": ["退款 1-3 天到账"], "reason": "上下文明确"},'
    '{"claim": "支持加急", "supported": false, "evidence": [], "reason": "上下文未提及"}'
    '], "reason": "ok"}'
)

CORRECTNESS_JSON = (
    '{"score": 0.8, "missing_points": ["到账时间"], "wrong_facts": [], "reason": "缺少到账说明"}'
)

RELEVANCY_JSON = '{"score": 0.9, "reason": "直接回答了问题"}'


class FakeLLM:
    """按顺序返回预设响应（字符串或异常对象）。"""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.last_messages: list[object] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        self.last_messages = list(messages)
        item = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return LLMResponse(
            content=str(item),
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="fake-judge-model",
            latency_ms=1.0,
        )

    async def aclose(self) -> None:
        return None


def _agent(metric: str, responses: list[object], **config) -> tuple[RagJudgeAgent, FakeLLM]:
    llm = FakeLLM(responses)
    agent = RagJudgeAgent(
        metric,  # type: ignore[arg-type]
        config=AgentConfig(
            name=f"rag_judge_{metric}",
            version="2026-11-14.1",
            max_retries=0,
            timeout=5.0,
            max_tokens=512,
            **config,
        ),
        llm=llm,
    )
    return agent, llm


def _faith_input(**overrides):
    payload = {
        "query": "退款多久到账？",
        "answer": "退款 1-3 天到账，支持加急。",
        "contexts": ["退款将在 1-3 天内到账。"],
    }
    payload.update(overrides)
    return payload


async def test_faithfulness_parses_claims() -> None:
    agent, llm = _agent("faithfulness", [FAITHFULNESS_JSON])

    result = await agent.judge(_faith_input())

    assert result.success is True
    assert result.data["claims"][0]["supported"] is True
    assert result.data["claims"][1]["supported"] is False
    assert result.raw_text == FAITHFULNESS_JSON
    assert llm.calls == 1


async def test_repair_round_raw_text_is_final_used_output() -> None:
    """首次输出非法 → 修复轮；raw_text 必须是修复后实际用于解析的文本。"""
    repaired = CORRECTNESS_JSON
    agent, llm = _agent("answer_correctness", ["not-json", repaired])

    result = await agent.judge({"query": "q", "answer": "a", "gold_answer": "g"})

    assert result.success is True
    assert result.data["score"] == 0.8
    assert llm.calls == 2
    assert result.raw_text == repaired


async def test_invalid_output_after_repair_fails_with_raw_text() -> None:
    agent, llm = _agent("answer_relevancy", ["not-json", "still-not-json"])

    result = await agent.judge({"query": "q", "answer": "a"})

    assert result.success is False
    assert any("StructuredOutputError" in error for error in result.errors)
    assert result.raw_text == "still-not-json"
    assert llm.calls == 2


async def test_faithfulness_requires_contexts_without_calling_llm() -> None:
    agent, llm = _agent("faithfulness", [FAITHFULNESS_JSON])

    result = await agent.judge({"query": "q", "answer": "a", "contexts": []})

    assert result.success is False
    assert any("contexts are required" in error for error in result.errors)
    assert llm.calls == 0


async def test_correctness_requires_gold_answer() -> None:
    agent, llm = _agent("answer_correctness", [CORRECTNESS_JSON])

    result = await agent.judge({"query": "q", "answer": "a"})

    assert result.success is False
    assert any("gold_answer is required" in error for error in result.errors)
    assert llm.calls == 0


async def test_relevancy_requires_answer() -> None:
    agent, llm = _agent("answer_relevancy", [RELEVANCY_JSON])

    result = await agent.judge({"query": "q", "answer": "  "})

    assert result.success is False
    assert llm.calls == 0


async def test_score_out_of_range_is_repaired_then_fails() -> None:
    invalid = '{"score": 1.5, "reason": "越界"}'
    agent, llm = _agent("answer_relevancy", [invalid, invalid])

    result = await agent.judge({"query": "q", "answer": "a"})

    assert result.success is False
    assert llm.calls == 2


async def test_timeout_is_reported_as_failure() -> None:
    agent, _ = _agent("answer_relevancy", [asyncio.TimeoutError("slow")])

    result = await agent.judge({"query": "q", "answer": "a"})

    assert result.success is False
    assert any("TimeoutError" in error for error in result.errors)


async def test_prompt_version_and_sha_are_exposed() -> None:
    agent, _ = _agent("faithfulness", [FAITHFULNESS_JSON])

    assert agent.config.version == "2026-11-14.1"
    assert len(agent.prompt_sha256) == 64
    assert agent.prompt_sha256 == agent.prompt_sha256
    assert agent.metric_version == "v1"


async def test_three_metrics_use_isolated_prompts() -> None:
    sha = {}
    for metric in ("faithfulness", "answer_correctness", "answer_relevancy"):
        agent, _ = _agent(metric, ["{}"])
        sha[metric] = agent.prompt_sha256

    assert len(set(sha.values())) == 3
