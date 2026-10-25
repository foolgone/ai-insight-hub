"""B-508 / B-510 报告 Agent 与模板测试。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import pytest

from app.agents.base import AgentConfig
from app.agents.report_agent import PROMPT_DIR, ReportGenerationAgent
from app.core.llm import LLMResponse, LLMUsage
from app.schemas.agents.report import REPORT_TYPES

pytestmark = pytest.mark.unit

TEMPLATE_DIR = PROMPT_DIR.parents[1] / "templates" / "reports"


def _valid_output() -> str:
    return json.dumps(
        {
            "summary": "整体质量良好，存在少量需复核项。",
            "sections": [
                {"title": "现状概览", "content": "共评估 100 条对话。"},
                {"title": "改进方向", "content": "补充售后话术。"},
            ],
            "highlights": ["平均总分 86.2"],
            "recommendations": ["补充低分维度的标准答案"],
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
            usage=LLMUsage(input_tokens=200, output_tokens=100),
            model="fake-model",
            latency_ms=10.0,
        )


def _agent(llm: _FakeLLM) -> ReportGenerationAgent:
    return ReportGenerationAgent(
        AgentConfig(name="report_agent", max_retries=0, retry_base_delay=0.0),
        llm=llm,
    )


def _input(
    report_type: str = "quality",
    data: dict[str, Any] | None = None,
    include_recommendations: bool = True,
) -> dict[str, Any]:
    return {
        "datasource_id": str(uuid.uuid4()),
        "title": "测试报告",
        "report_type": report_type,
        "data": data if data is not None else {"quality": {"total": 10, "avg_overall_score": 86.2}},
        "config": {"include_recommendations": include_recommendations},
    }


def test_report_templates_one_to_one() -> None:
    assert (PROMPT_DIR / "system.txt").is_file()
    for report_type in REPORT_TYPES:
        template = TEMPLATE_DIR / f"{report_type}.md"
        assert template.is_file(), f"missing template for {report_type}"
        body = template.read_text(encoding="utf-8")
        assert "__TITLE__" in body
        assert "__SECTIONS__" in body


async def test_generate_success() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.generate(_input())

    assert result.success is True
    data = result.data or {}
    assert data["title"] == "测试报告"
    assert data["report_type"] == "quality"
    assert len(data["sections"]) == 2
    assert data["recommendations"] == ["补充低分维度的标准答案"]
    assert datetime.fromisoformat(data["generated_at"])
    assert data["metadata"]["insight_degraded"] is False


async def test_generate_comprehensive_insight_degraded() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.generate(
        _input(
            report_type="comprehensive",
            data={"quality": {}, "knowledge": {}, "insight": None},
        )
    )

    data = result.data or {}
    assert data["metadata"]["insight_degraded"] is True


async def test_generate_without_recommendations() -> None:
    llm = _FakeLLM([_valid_output()])
    agent = _agent(llm)

    result = await agent.generate(_input(include_recommendations=False))

    assert result.success is True
    assert (result.data or {})["recommendations"] == []


async def test_generate_invalid_input() -> None:
    llm = _FakeLLM([])
    agent = _agent(llm)

    result = await agent.generate(_input(data={}))

    assert result.success is False
    assert any("AgentInputError" in item for item in result.errors)
    assert llm.calls == []


async def test_generate_rejects_empty_sections() -> None:
    llm = _FakeLLM([json.dumps({"summary": "s", "sections": [], "recommendations": []})])
    agent = _agent(llm)

    result = await agent.generate(_input())

    assert result.success is False
    assert any("AgentOutputError" in item for item in result.errors)


async def test_generate_repairs_invalid_json() -> None:
    llm = _FakeLLM(["not json", _valid_output()])
    agent = _agent(llm)

    result = await agent.generate(_input())

    assert result.success is True
    assert len(llm.calls) == 2
