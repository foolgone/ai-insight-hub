"""B-104：成本追踪 POC（usage 直读 + 单价公式）。

验证：token 统计口径、成本公式、单价未配置时的告警语义。
真实成本落库（``llm_calls``）在 B-306 实现，本 POC 不写库。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.llm import LLMResponse, LLMUsage

pytestmark = pytest.mark.slow


def compute_cost(usage: LLMUsage, price_input: Decimal, price_output: Decimal) -> Decimal:
    """单次成本（USD）= (输入token×P_IN + 输出token×P_OUT) / 1_000_000。

    单价单位：USD / 百万 token；代码不写死单价（配置注入）。
    """
    return (
        Decimal(usage.input_tokens) * price_input + Decimal(usage.output_tokens) * price_output
    ) / Decimal(1_000_000)


def test_cost_formula_is_exact() -> None:
    p_in, p_out = Decimal("1.0"), Decimal("2.0")

    assert compute_cost(LLMUsage(1_000_000, 0), p_in, p_out) == Decimal("1.0")
    assert compute_cost(LLMUsage(0, 1_000_000), p_in, p_out) == Decimal("2.0")
    assert compute_cost(LLMUsage(500_000, 250_000), p_in, p_out) == Decimal("1.0")
    print("\n[POC-4] 公式校验通过（P_IN=1.0 / P_OUT=2.0）")


def test_cost_matches_token_breakdown() -> None:
    p_in, p_out = Decimal("0.27"), Decimal("1.10")
    usage = LLMUsage(input_tokens=1234, output_tokens=567)
    expected = (Decimal(1234) * p_in + Decimal(567) * p_out) / Decimal(1_000_000)
    assert compute_cost(usage, p_in, p_out) == expected
    print(f"\n[POC-4] 1234/567 tokens → ${expected:.8f}")


def test_usage_totals() -> None:
    usage = LLMUsage(input_tokens=120, output_tokens=30)
    assert usage.total_tokens == 150
    assert LLMUsage.from_api({"prompt_tokens": 7, "completion_tokens": 3}).total_tokens == 10
    assert LLMUsage.from_api(None).total_tokens == 0


def test_response_carries_usage_for_cost() -> None:
    """成本只依赖 LLMResponse.usage，不依赖任何框架回调。"""
    resp = LLMResponse(
        content="ok",
        usage=LLMUsage(100, 50),
        model=settings.DEFAULT_LLM_MODEL,
        latency_ms=12.5,
    )
    cost = compute_cost(
        resp.usage,
        Decimal(str(settings.LLM_PRICE_INPUT_PER_MTOK)),
        Decimal(str(settings.LLM_PRICE_OUTPUT_PER_MTOK)),
    )
    assert cost == Decimal("0")  # 当前单价未配置（D-09）
    print(f"\n[POC-4] response.usage={resp.usage} cost=${cost}")


def test_price_not_configured_is_detectable() -> None:
    """D-09 未解决时：单价=0 可被检测，成本链路会空转，必须告警。"""
    if settings.LLM_PRICE_INPUT_PER_MTOK <= 0 or settings.LLM_PRICE_OUTPUT_PER_MTOK <= 0:
        print(
            "\n[POC-4] ⚠️ LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK 未配置"
            "（当前为 0），成本恒为 0，四档告警与降级不会触发（上线阻断项 D-09）"
        )
    assert settings.LLM_PRICE_INPUT_PER_MTOK >= 0
    assert settings.LLM_PRICE_OUTPUT_PER_MTOK >= 0
