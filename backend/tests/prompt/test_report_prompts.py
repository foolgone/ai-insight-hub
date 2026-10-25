"""B-607 报告 Prompt 测试（50 条，默认排除：pytest -m prompt）。"""
from __future__ import annotations

import uuid

import pytest

from app.agents.report_agent import ReportGenerationAgent
from app.core.llm import LLMClient

pytestmark = [pytest.mark.prompt, pytest.mark.slow]

_TYPES = ["quality", "knowledge", "insight", "comprehensive"]

_DATA_VARIANTS = [
    {"quality": {"total": 10, "avg_overall_score": 86.2}},
    {"knowledge": {"total": 50, "seed": 12, "stage": "ready"}},
    {"insight": {"intent_distribution": {"咨询": 8, "投诉": 2}}},
    {
        "quality": {"total": 5, "avg_overall_score": 62},
        "knowledge": {"total": 3},
        "insight": None,
    },
    {
        "quality": {"total": 100, "avg_overall_score": 91},
        "knowledge": {"total": 200},
        "insight": {"summary": "投诉下降"},
    },
    {"quality": {"total": 0, "avg_overall_score": 0}, "knowledge": {"total": 0}},
    {"knowledge": {"total": 120, "stage": "warming", "gaps_count": 8}},
    {"insight": {"pain_points": [{"issue": "退货流程", "frequency": 30}]}},
    {
        "quality": {"total": 30, "avg_overall_score": 78},
        "knowledge": {"total": 45, "stage": "warming"},
    },
    {
        "quality": {"total": 60, "avg_overall_score": 95},
        "knowledge": {"total": 80, "stage": "ready"},
        "insight": {"emerging_topics": ["新品咨询"]},
    },
]

_CONFIGS = [
    {"include_charts": True, "include_recommendations": True},
    {"include_charts": False, "include_recommendations": True},
    {"include_charts": True, "include_recommendations": False},
    {"include_charts": False, "include_recommendations": False},
    {
        "include_charts": True,
        "include_recommendations": True,
        "time_range": {"start": "2025-01-01", "end": "2025-01-31"},
    },
]

CASES = [
    {
        "report_type": _TYPES[(index + variant) % len(_TYPES)],
        "title": f"报告-{index}-{variant}",
        "data": data,
        "config": config,
    }
    for index, data in enumerate(_DATA_VARIANTS)
    for variant, config in enumerate(_CONFIGS)
]


def _require_llm() -> None:
    if not LLMClient().is_configured:
        pytest.skip("DEEPSEEK_API_KEY 未配置，跳过 Prompt 测试")


@pytest.mark.parametrize("case", CASES)
async def test_report_prompt_returns_valid_sections(case: dict) -> None:
    _require_llm()
    agent = ReportGenerationAgent()

    result = await agent.generate(
        {
            "datasource_id": str(uuid.uuid4()),
            "title": case["title"],
            "report_type": case["report_type"],
            "data": case["data"],
            "config": case["config"],
        }
    )

    assert result.success, result.errors
    data = result.data or {}
    assert data["title"] == case["title"]
    assert data["sections"]
    assert data["summary"]
    assert data["metadata"]["data_keys"]


def test_report_prompt_case_count() -> None:
    assert len(CASES) == 50
