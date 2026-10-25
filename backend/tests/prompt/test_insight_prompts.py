"""B-607 洞察 Prompt 测试（50 条，默认排除：pytest -m prompt）。"""
from __future__ import annotations

import uuid

import pytest

from app.agents.insight_agent import InsightAnalysisAgent
from app.core.llm import LLMClient

pytestmark = [pytest.mark.prompt, pytest.mark.slow]

_BATCHES = [
    [("iPhone 14 多少钱", "5999 元起")],
    [("退货怎么操作", "订单页申请"), ("发票能开吗", "下单填写抬头")],
    [("多久发货", "48 小时"), ("可以分期吗", "支持 12 期免息")],
    [("保修多久", "整机一年"), ("能便宜点吗", "已是最低价")],
    [("包装有哪些配件", "数据线说明书"), ("支持以旧换新吗", "支持")],
    [("怎么转人工", "输入转人工"), ("物流到哪了", "订单页查看")],
    [("有优惠券吗", "结算页可用"), ("可以改地址吗", "未发货可改")],
    [("退款多久到账", "1-3 个工作日"), ("能开发票吗", "可以")],
    [("商品有货吗", "现货"), ("多久到货", "2-4 天")],
    [("质量怎么样", "官方正品"), ("售后好吗", "一年保修")],
]

_CONFIGS = [
    {},
    {"analyze_sentiment": False},
    {"identify_trends": False},
    {"find_pain_points": False},
    {
        "analyze_sentiment": True,
        "identify_trends": True,
        "find_pain_points": True,
    },
]

CASES = [
    {
        "dialogues": [
            {
                "dialogue_id": f"insight-{batch_index}-{index}",
                "timestamp": f"2025-01-{15 + batch_index:02d}T10:00:00",
                "user_message": user_message,
                "ai_response": ai_response,
            }
            for index, (user_message, ai_response) in enumerate(batch)
        ],
        "config": config,
    }
    for batch_index, batch in enumerate(_BATCHES)
    for config in _CONFIGS
]


def _require_llm() -> None:
    if not LLMClient().is_configured:
        pytest.skip("DEEPSEEK_API_KEY 未配置，跳过 Prompt 测试")


@pytest.mark.parametrize("case", CASES)
async def test_insight_prompt_returns_valid_structure(case: dict) -> None:
    _require_llm()
    agent = InsightAnalysisAgent()

    result = await agent.analyze(
        {
            "datasource_id": str(uuid.uuid4()),
            "dialogues": case["dialogues"],
            "config": case["config"],
        }
    )

    assert result.success, result.errors
    data = result.data or {}
    assert isinstance(data["intent_distribution"], dict)
    assert data["intent_distribution"]
    assert isinstance(data["top_questions"], list)
    sentiment = data["sentiment_distribution"]
    if sentiment:
        assert set(sentiment) <= {"正面", "中性", "负面"}
        assert round(sum(sentiment.values()), 3) == 1.0
    assert isinstance(data["pain_points"], list)
    assert isinstance(data["emerging_topics"], list)


def test_insight_prompt_case_count() -> None:
    assert len(CASES) == 50
