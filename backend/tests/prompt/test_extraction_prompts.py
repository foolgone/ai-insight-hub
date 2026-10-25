"""B-507 知识提取 Prompt 测试骨架（真实 LLM，默认排除：pytest -m prompt）。"""
from __future__ import annotations

import uuid

import pytest

from app.agents.extraction_agent import KnowledgeExtractionAgent
from app.core.llm import LLMClient

pytestmark = [pytest.mark.prompt, pytest.mark.slow]

_QA_PAIRS = [
    ("iPhone 14 多少钱", "5999 元起，支持 12 期免息"),
    ("退货怎么操作", "在订单页点击申请退货即可"),
    ("可以分期吗", "支持花呗 12 期免息"),
    ("发票能开吗", "可以，下单时填写抬头即可"),
    ("多久发货", "48 小时内发出"),
    ("保修多久", "整机保修一年"),
    ("支持以旧换新吗", "支持，可在结算页选择"),
    ("这个和上一代有什么区别", "芯片和续航都有提升"),
    ("能便宜点吗", "抱歉，当前价格已是最低"),
    ("包装里有哪些配件", "数据线、说明书和取卡针"),
]

_PREFIXES = [
    "",
    "2025-01-15 10:30:00 ",
    "2025/01/16 09:05:00 ",
    "2025-01-17 ",
    "2025年1月18日 10:30 ",
]

CASES = [
    {
        "dialogue_id": f"prompt-{index}",
        "user_message": f"{prefix}客户：{question}",
        "ai_response": f"客服：{answer}",
    }
    for question, answer in _QA_PAIRS
    for index, prefix in enumerate(_PREFIXES, start=1)
]


def _require_llm() -> None:
    if not LLMClient().is_configured:
        pytest.skip("DEEPSEEK_API_KEY 未配置，跳过 Prompt 测试")


@pytest.mark.parametrize("dialogue", CASES)
async def test_extraction_prompt_returns_valid_faqs(dialogue: dict) -> None:
    _require_llm()
    agent = KnowledgeExtractionAgent()

    result = await agent.extract(
        {
            "datasource_id": str(uuid.uuid4()),
            "dialogues": [dialogue],
            "existing_questions": [],
        }
    )

    assert result.success, result.errors
    data = result.data or {}
    assert data["faqs"]
    for faq in data["faqs"]:
        assert faq["question"].strip()
        assert faq["answer"].strip()
        assert 0 <= faq["confidence"] <= 1
        assert faq["embedding"] is not None or data["stats"]["embedding_failed"] > 0
    assert isinstance(data["gaps"], list)


def test_extraction_prompt_case_count() -> None:
    assert len(CASES) == 50
