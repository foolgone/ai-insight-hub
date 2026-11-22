"""Shared v3 evidence quote validator tests (no Judge, no DB)."""
from __future__ import annotations

import pytest

from app.schemas.agents.rag_judge_evidence import (
    QuoteContractError,
    build_context_map,
    check_claims_evidence,
    check_quote,
    detect_mixed_absence,
    format_quote_contract_error,
    quote_validator_sha256,
)

pytestmark = pytest.mark.unit

CONTEXT = "商品签收后不支持无理由退货；出现质量问题的，需在签收后 24 小时内提交照片反馈。\n" "第二句用于测试完整句子窗口。"
TRUNCATED = "商品出现质量问题时可在 24 小时内反馈。"
CONTIGUOUS = "出现质量问题的，需在签收后 24 小时内提交照片反馈。"


def test_contiguous_quote_passes() -> None:
    check = check_quote(
        quote=CONTIGUOUS,
        context_id="C1",
        context_map=build_context_map([CONTEXT]),
        claim_id="cl1",
    )

    assert check.ok is True
    assert check.error is None


def test_answer_truncated_quote_is_not_found() -> None:
    check = check_quote(
        quote=TRUNCATED,
        context_id="C1",
        context_map=build_context_map([CONTEXT]),
        claim_id="cl1",
    )

    assert check.ok is False
    assert check.error == "quote_not_found"
    assert check.context_excerpt
    assert check.context_excerpt.startswith("商品签收后不支持无理由退货")


def test_unknown_context_and_empty_quote() -> None:
    context_map = build_context_map([CONTEXT])

    unknown = check_quote(
        quote=CONTIGUOUS,
        context_id="C9",
        context_map=context_map,
        claim_id="cl1",
    )
    empty = check_quote(
        quote="  ",
        context_id="C1",
        context_map=context_map,
        claim_id="cl2",
    )

    assert unknown.error == "unknown_context_id"
    assert empty.error == "empty_quote"


def test_quote_is_stripped_before_check() -> None:
    check = check_quote(
        quote=f"  {CONTIGUOUS}  ",
        context_id="C1",
        context_map=build_context_map([CONTEXT]),
        claim_id="cl1",
    )

    assert check.ok is True


def test_claims_evidence_preserves_order() -> None:
    claims = [
        {
            "claim_id": "cl1",
            "claim_type": "factual_claim",
            "evidence_refs": [{"context_id": "C1", "quote": CONTIGUOUS}],
        },
        {
            "claim_id": "cl2",
            "claim_type": "factual_claim",
            "evidence_refs": [{"context_id": "C1", "quote": TRUNCATED}],
        },
        {
            "claim_id": "cl3",
            "claim_type": "non_factual",
            "evidence_refs": [],
        },
    ]

    checks = check_claims_evidence(claims, build_context_map([CONTEXT]))

    assert [check.claim_id for check in checks] == ["cl1", "cl2"]
    assert [check.ok for check in checks] == [True, False]


def test_error_message_is_bounded() -> None:
    checks = [
        check_quote(
            quote=f"missing quote {index}",
            context_id="C1",
            context_map=build_context_map([CONTEXT]),
            claim_id=f"cl{index}",
        )
        for index in range(1, 11)
    ]

    message = format_quote_contract_error(checks)

    assert "quote_contract_violation" in message
    assert "cl1" in message and "cl5" in message
    assert "more error(s)" in message
    assert len(message) <= 2000
    assert "do not copy answer" in message


def test_mixed_absence_detection() -> None:
    assert detect_mixed_absence("该时限是硬性要求，文档未提及例外情形或宽限期") is True
    assert detect_mixed_absence("文档未说明超时后的申诉渠道") is False
    assert detect_mixed_absence("该时限是硬性要求") is False
    assert detect_mixed_absence("建议联系客服") is False


def test_quote_contract_error_is_value_error() -> None:
    assert issubclass(QuoteContractError, ValueError)


def test_validator_sha_is_stable() -> None:
    assert len(quote_validator_sha256()) == 64
