"""B-306 成本计算单测（纯函数，不连库）。"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.cost_tracker import CostTracker, compute_cost
from app.core.llm import LLMUsage

pytestmark = pytest.mark.unit


def test_compute_cost_input_and_output() -> None:
    breakdown = compute_cost(
        LLMUsage(input_tokens=1_000_000, output_tokens=0),
        price_input=Decimal("1.0"),
        price_output=Decimal("2.0"),
    )
    assert breakdown.input_cost == Decimal("1.00000000")
    assert breakdown.output_cost == Decimal("0.00000000")
    assert breakdown.total_cost == Decimal("1.00000000")

    breakdown = compute_cost(
        LLMUsage(input_tokens=0, output_tokens=1_000_000),
        price_input=Decimal("1.0"),
        price_output=Decimal("2.0"),
    )
    assert breakdown.total_cost == Decimal("2.00000000")


def test_compute_cost_fractional_tokens() -> None:
    breakdown = compute_cost(
        LLMUsage(input_tokens=1234, output_tokens=567),
        price_input=Decimal("0.27"),
        price_output=Decimal("1.10"),
    )
    expected = (Decimal(1234) * Decimal("0.27") + Decimal(567) * Decimal("1.10")) / Decimal(
        1_000_000
    )
    assert breakdown.total_cost == expected.quantize(Decimal("0.00000001"))


def test_compute_cost_zero_price_returns_zero(monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_MTOK", 0.0)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_MTOK", 0.0)

    breakdown = compute_cost(LLMUsage(input_tokens=1000, output_tokens=1000))

    assert breakdown.total_cost == Decimal("0.00000000")


@pytest.mark.parametrize(
    ("task_id", "attempt", "expected"),
    [
        ("task-1", 0, "task-1:0"),
        (
            uuid.UUID("00000000-0000-0000-0000-000000000001"),
            2,
            "00000000-0000-0000-0000-000000000001:2",
        ),
        (None, 0, "adhoc:0"),
        (None, 3, "adhoc:3"),
    ],
)
def test_idempotency_key(task_id, attempt, expected) -> None:
    assert CostTracker.idempotency_key(task_id, attempt) == expected
