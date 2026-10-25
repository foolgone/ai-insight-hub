"""B-405 评估 Prompt 测试骨架（真实 LLM，默认排除：pytest -m prompt）。"""
from __future__ import annotations

import uuid

import pytest

from app.agents.evaluation_agent import QualityEvaluationAgent
from app.core.llm import LLMClient

pytestmark = [pytest.mark.prompt, pytest.mark.slow]

_DIALOGUES = [
    ("iPhone 14 多少钱", "5999 元起，支持 12 期免息。"),
    ("退货怎么操作", "在订单页点击申请退货即可。"),
    ("可以分期吗", "支持花呗 12 期免息。"),
    ("发票能开吗", "可以，下单时填写抬头即可。"),
    ("多久发货", "48 小时内发出。"),
    ("保修多久", "整机保修一年。"),
    ("支持以旧换新吗", "支持，可在结算页选择以旧换新。"),
    ("这个和上一代有什么区别", "芯片和续航都有提升。"),
    ("能便宜点吗", "抱歉，当前价格已是最低。"),
    ("包装里有哪些配件", "数据线、说明书和取卡针。"),
]

_KNOWLEDGE_BASE = [{"question": "iPhone 14 价格", "answer": "5999 元起"}]

CASES = [
    {
        "dialogue": {
            "dialogue_id": f"prompt-{index}",
            "user_message": user_message,
            "ai_response": ai_response,
        },
        "knowledge_base": _KNOWLEDGE_BASE,
    }
    for index, (user_message, ai_response) in enumerate(_DIALOGUES, start=1)
]


def _require_llm() -> None:
    if not LLMClient().is_configured:
        pytest.skip("DEEPSEEK_API_KEY 未配置，跳过 Prompt 测试")


@pytest.mark.parametrize("case", CASES)
async def test_evaluation_prompt_returns_valid_scores(case: dict) -> None:
    _require_llm()
    agent = QualityEvaluationAgent()

    result = await agent.evaluate({**case, "datasource_id": str(uuid.uuid4())})

    assert result.success, result.errors
    data = result.data or {}
    assert 0 <= data["overall_score"] <= 100
    assert set(data["dimensions"]) == {
        "accuracy",
        "completeness",
        "hallucination",
        "tone",
        "compliance",
    }
    for dimension in data["dimensions"].values():
        assert 0 <= dimension["score"] <= 100
    assert data["quality_level"] in {"excellent", "good", "fair", "poor"}
    assert data["needs_review"] == (data["overall_score"] < 70)


def test_evaluation_prompt_case_count() -> None:
    assert len(CASES) == 10
