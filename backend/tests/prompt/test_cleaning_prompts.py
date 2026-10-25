"""B-315 清洗 Prompt 测试骨架（真实 LLM，默认排除）。

运行方式：``pytest -m prompt tests/prompt -v``（会产生真实 token 费用）。
每个用例校验输出结构与质量分范围；语义/金标准对比见 ``golden_outputs/README.md``。
"""
from __future__ import annotations

import uuid

import pytest

from app.agents.cleaning_agent import DataCleaningAgent
from app.core.llm import LLMClient

pytestmark = [pytest.mark.prompt, pytest.mark.slow]

_QUESTIONS = [
    "iPhone 14 多少钱",
    "退货怎么操作",
    "可以分期吗",
    "发票能开吗",
    "多久发货",
    "保修多久",
    "支持以旧换新吗",
    "这个和上一代有什么区别",
    "能便宜点吗",
    "包装里有哪些配件",
]

_TIMESTAMP_PREFIXES = [
    "",
    "2025-01-15 10:30:00 ",
    "2025/01/16 09:05:00 ",
    "2025-01-17 ",
    "2025年1月18日 10:30 ",
]

# 10 个问题 × 5 种时间戳格式 = 50 条用例
CASES = [
    f"{prefix}客户：{question} 客服：这是标准回复。" for question in _QUESTIONS for prefix in _TIMESTAMP_PREFIXES
]


def _require_llm() -> None:
    if not LLMClient().is_configured:
        pytest.skip("DEEPSEEK_API_KEY 未配置，跳过 Prompt 测试")


@pytest.mark.parametrize("raw_data", CASES)
async def test_cleaning_prompt_returns_valid_structure(raw_data: str) -> None:
    _require_llm()
    agent = DataCleaningAgent()

    result = await agent.clean(
        {
            "datasource_id": str(uuid.uuid4()),
            "raw_data": raw_data,
            "data_type": "txt",
        }
    )

    assert result.success, result.errors
    data = result.data or {}
    assert data["cleaned_records"] >= 1
    assert data["total_records"] >= data["cleaned_records"]
    assert 0 <= data["statistics"]["avg_quality_score"] <= 100
    for dialogue in data["dialogues"]:
        assert isinstance(dialogue["user_message"], str)
        assert isinstance(dialogue["ai_response"], str)
        assert 0 <= dialogue["quality_score"] <= 100
        assert "user_message" in dialogue and "ai_response" in dialogue


def test_prompt_case_count() -> None:
    assert len(CASES) == 50
