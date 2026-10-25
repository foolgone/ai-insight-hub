"""B-101：LLM 协议验证（无框架）——调用、JSON 输出、usage 可读。

真实调用需要有效 ``DEEPSEEK_API_KEY``；未配置时 skip 并在 POC 报告记为待验证。
"""
from __future__ import annotations

import json
import time

import pytest

from app.core.config import settings
from app.core.llm import LLMClient

from tests.poc.conftest import skip_without_llm

pytestmark = pytest.mark.slow


async def test_llm_basic_call() -> None:
    """基础调用：内容非空、模型 id 来自配置、耗时与 usage 可读。"""
    skip_without_llm()
    async with LLMClient() as llm:
        started = time.perf_counter()
        resp = await llm.chat(
            [
                {"role": "system", "content": "你是一个 AI 助手，回答简洁。"},
                {"role": "user", "content": "用一句话介绍 Python。"},
            ]
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

    assert resp.content.strip(), "响应内容为空"
    assert resp.model == settings.DEFAULT_LLM_MODEL
    assert resp.usage.total_tokens > 0
    assert resp.latency_ms > 0
    print(
        f"\n[POC-1] 调用成功 model={resp.model} tokens={resp.usage} "
        f"latency={resp.latency_ms:.0f}ms (实测总耗时 {elapsed_ms:.0f}ms)"
    )


async def test_llm_json_output() -> None:
    """结构化输出：JSON 可解析，失败率需记录（单次 POC 以可解析为通过）。"""
    skip_without_llm()
    async with LLMClient() as llm:
        resp = await llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是数据清洗助手。只输出 JSON，不要输出其它内容。"
                        '格式：{"user_message": "...", "ai_response": "..."}'
                    ),
                },
                {
                    "role": "user",
                    "content": '文本："用户：iPhone 14 多少钱？客服：5999 元起"',
                },
            ],
            response_format={"type": "json_object"},
        )

    try:
        data = json.loads(resp.content)
    except ValueError as exc:  # pragma: no cover - 依赖真实模型输出
        pytest.fail(f"JSON 解析失败（需记录失败率）：{exc}\n原始内容：{resp.content[:200]}")

    assert "user_message" in data and "ai_response" in data
    print(f"\n[POC-1] JSON 解析成功：{data}")


async def test_llm_usage_is_consistent() -> None:
    """usage 直读：input/output ≥ 0 且 total = input + output（成本计算前提）。"""
    skip_without_llm()
    async with LLMClient() as llm:
        resp = await llm.chat([{"role": "user", "content": "hi"}])

    assert resp.usage.input_tokens >= 0
    assert resp.usage.output_tokens >= 0
    assert resp.usage.total_tokens == resp.usage.input_tokens + resp.usage.output_tokens
    print(f"\n[POC-1] usage 口径：{resp.usage}")
