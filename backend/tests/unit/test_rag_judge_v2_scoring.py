"""v1.1.1 Faithfulness 计分/证据/矛盾规则 + 六案例边界回归。"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from app.agents.base import AgentResult
from app.core.config import settings
from app.models import RagEvaluationResult, RagTrace
from app.schemas.agents.rag_judge import JUDGE_SCHEMA_V1, JUDGE_SCHEMA_V2
from app.services.rag_evaluation_service import (
    build_aggregate,
    build_judge_config,
    metric_version_for,
)
from app.services.rag_judge_service import _faithfulness_score, judge_trace

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / "docs" / "repair" / "phase3e" / "prompt-v1.1.1-acceptance-matrix.json"
FIXTURES_PATH = REPO_ROOT / "docs" / "repair" / "phase3e" / "prompt-v1.1.1-fixtures.json"

CONTEXTS = [
    "订单签收后 7 天内可申请无理由退款。",
    "质量问题需在签收后 24 小时内拍照反馈。",
]


def _claim(**overrides: Any) -> dict[str, Any]:
    base = {
        "claim_id": "cl1",
        "claim": "订单签收后 7 天内可申请无理由退款",
        "claim_type": "factual_claim",
        "claim_subtype": "policy",
        "support_status": "supported",
        "is_contradictory": False,
        "contradiction_with": [],
        "evidence_refs": [{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
        "reason": "test",
    }
    base.update(overrides)
    return base


def _score(
    claims: list[dict[str, Any]], **kwargs: Any
) -> tuple[float | None, dict[str, Any], str | None]:
    return _faithfulness_score(
        {"claims": claims, "reason": "test"},
        contexts=kwargs.pop("contexts", CONTEXTS),
        schema_version=kwargs.pop("schema_version", JUDGE_SCHEMA_V2),
        **kwargs,
    )


# --------------------------------------------------------------------------- 基础计分


def test_all_non_factual_is_skipped_not_one() -> None:
    score, details, reason = _score(
        [
            _claim(
                claim_type="non_factual",
                claim_subtype="absence",
                support_status=None,
                evidence_refs=[],
            ),
            _claim(
                claim_id="cl2",
                claim_type="non_factual",
                claim_subtype="advice",
                support_status=None,
                evidence_refs=[],
            ),
        ]
    )

    assert score is None
    assert reason == "no_scorable_claims"
    assert details["scorable_claim_count"] == 0
    assert details["non_factual_count"] == 2


def test_all_insufficient_is_evaluated_zero() -> None:
    score, details, reason = _score(
        [
            _claim(support_status="insufficient_evidence", evidence_refs=[]),
            _claim(
                claim_id="cl2",
                support_status="insufficient_evidence",
                evidence_refs=[],
            ),
        ]
    )

    assert score == 0.0
    assert reason is None
    assert details["all_insufficient"] is True
    assert details["insufficient_evidence_count"] == 2


def test_mixed_supported_unsupported_insufficient() -> None:
    score, details, _ = _score(
        [
            _claim(),
            _claim(
                claim_id="cl2",
                support_status="unsupported",
                evidence_refs=[],
            ),
            _claim(
                claim_id="cl3",
                support_status="insufficient_evidence",
                evidence_refs=[],
            ),
        ]
    )

    assert score == pytest.approx(1 / 3)
    assert details["supported_claim_count"] == 1
    assert details["unsupported_claim_count"] == 1
    assert details["insufficient_evidence_count"] == 1


def test_non_factual_excluded_from_denominator() -> None:
    score, details, _ = _score(
        [
            _claim(),
            _claim(
                claim_id="cl2",
                claim_type="non_factual",
                claim_subtype="absence",
                support_status=None,
                evidence_refs=[],
            ),
        ]
    )

    assert score == 1.0
    assert details["scorable_claim_count"] == 1
    assert details["non_factual_count"] == 1


def test_contradictory_claim_stays_in_denominator() -> None:
    score, details, _ = _score(
        [
            _claim(
                claim="可以按政策反馈",
                support_status="unsupported",
                is_contradictory=True,
                contradiction_with=["cl2"],
                evidence_refs=[],
            ),
            _claim(
                claim_id="cl2",
                claim="超过 24 小时反馈不符合受理条件",
                support_status="supported",
                evidence_refs=[{"context_id": "C2", "quote": "质量问题需在签收后 24 小时内拍照反馈。"}],
            ),
        ]
    )

    assert score == 0.5
    assert details["scorable_claim_count"] == 2
    assert details["contradiction_count"] == 1


def test_duplicate_supported_claim_counts_once() -> None:
    score, details, _ = _score(
        [
            _claim(),
            _claim(claim="重复的同一 claim", claim_id="cl1"),
        ]
    )

    assert score == 1.0
    assert details["scorable_claim_count"] == 1
    assert details["supported_claim_count"] == 1
    assert len(details["claims"]) == 1
    assert any(error["code"] == "duplicate_claim_id" for error in details["validation_errors"])


def test_duplicate_unsupported_claim_counts_once() -> None:
    score, details, _ = _score(
        [
            _claim(claim_id="cl1"),
            _claim(claim_id="cl2", support_status="unsupported", evidence_refs=[]),
            _claim(claim_id="cl2", support_status="unsupported", evidence_refs=[]),
        ]
    )

    assert score == 0.5
    assert details["scorable_claim_count"] == 2
    assert details["supported_claim_count"] == 1
    assert details["unsupported_claim_count"] == 1
    assert len(details["claims"]) == 2
    assert any(error["code"] == "duplicate_claim_id" for error in details["validation_errors"])


# --------------------------------------------------------------------------- 证据


def test_supported_without_evidence_is_downgraded() -> None:
    score, details, _ = _score([_claim(evidence_refs=[])])

    assert score == 0.0
    assert details["claims"][0]["support_status"] == "insufficient_evidence"
    assert details["evidence_validation_failed"] is True
    assert details["all_insufficient"] is True
    assert any(
        error["code"] == "supported_without_evidence" for error in details["validation_errors"]
    )


def test_quote_not_verbatim_is_downgraded() -> None:
    score, details, _ = _score([_claim(evidence_refs=[{"context_id": "C1", "quote": "上下文里没有这句话"}])])

    assert score == 0.0
    assert details["claims"][0]["support_status"] == "insufficient_evidence"
    assert details["evidence_validation"][0]["error"] == "quote_not_found"
    assert any(error["code"] == "quote_not_found" for error in details["validation_errors"])


def test_unknown_context_is_downgraded() -> None:
    score, details, _ = _score(
        [_claim(evidence_refs=[{"context_id": "C9", "quote": "订单签收后 7 天内可申请无理由退款。"}])]
    )

    assert score == 0.0
    assert details["evidence_validation"][0]["error"] == "unknown_context_id"
    assert any(error["code"] == "unknown_context_id" for error in details["validation_errors"])


def test_empty_quote_is_downgraded() -> None:
    score, details, _ = _score([_claim(evidence_refs=[{"context_id": "C1", "quote": "   "}])])

    assert score == 0.0
    assert details["evidence_validation"][0]["error"] == "empty_quote"


def test_insufficient_claim_may_have_no_evidence() -> None:
    score, details, _ = _score([_claim(support_status="insufficient_evidence", evidence_refs=[])])

    assert score == 0.0
    assert details["evidence_validation_failed"] is False
    assert details["validation_errors"] == []


# --------------------------------------------------------------------------- 矛盾 / subtype


def test_conflict_claim_must_not_be_contradictory() -> None:
    score, details, _ = _score(
        [
            _claim(
                claim_subtype="conflict",
                is_contradictory=True,
                contradiction_with=["cl1"],
                evidence_refs=[
                    {"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"},
                    {"context_id": "C2", "quote": "质量问题需在签收后 24 小时内拍照反馈。"},
                ],
            )
        ]
    )

    assert score == 1.0
    assert details["claims"][0]["is_contradictory"] is False
    assert details["contradiction_count"] == 0
    assert details["document_conflict"] is True
    assert any(
        error["code"] == "conflict_marked_contradictory" for error in details["validation_errors"]
    )


def test_conflict_claim_needs_two_sided_evidence() -> None:
    score, details, _ = _score(
        [
            _claim(
                claim_subtype="conflict",
                evidence_refs=[{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
            )
        ]
    )

    assert score == 0.0
    assert details["claims"][0]["support_status"] == "insufficient_evidence"
    assert details["document_conflict"] is False
    assert any(
        error["code"] == "conflict_single_sided_evidence" for error in details["validation_errors"]
    )


def test_conflict_duplicate_quote_is_downgraded() -> None:
    ref = {"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}

    score, details, _ = _score([_claim(claim_subtype="conflict", evidence_refs=[ref, dict(ref)])])

    assert score == 0.0
    assert details["claims"][0]["support_status"] == "insufficient_evidence"
    assert details["document_conflict"] is False
    assert any(
        error["code"] == "conflict_single_sided_evidence" for error in details["validation_errors"]
    )


def test_conflict_nested_quote_is_downgraded() -> None:
    score, details, _ = _score(
        [
            _claim(
                claim_subtype="conflict",
                evidence_refs=[
                    {"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"},
                    {"context_id": "C1", "quote": "订单签收后 7 天内"},
                ],
            )
        ]
    )

    assert score == 0.0
    assert details["claims"][0]["support_status"] == "insufficient_evidence"
    assert details["document_conflict"] is False
    assert any(
        error["code"] == "conflict_single_sided_evidence" for error in details["validation_errors"]
    )


def test_factual_missing_support_status_is_not_supported() -> None:
    claim = _claim()
    claim.pop("support_status")
    claim["supported"] = True

    score, details, _ = _score([claim])

    assert score == 0.0
    assert details["claims"][0]["support_status"] == "insufficient_evidence"
    assert any(error["code"] == "support_status_invalid" for error in details["validation_errors"])


def test_invalid_claim_subtype_is_normalized_with_error() -> None:
    score, details, _ = _score([_claim(claim_subtype="advice")])

    assert score == 1.0
    assert details["claims"][0]["claim_subtype"] == "policy"
    assert any(
        error["code"] == "claim_subtype_type_mismatch" for error in details["validation_errors"]
    )


def test_invalid_claim_type_is_normalized_to_factual() -> None:
    claim = _claim()
    claim["claim_type"] = "policy"

    score, details, _ = _score([claim])

    assert score == 1.0
    assert details["claims"][0]["claim_type"] == "factual_claim"
    assert any(error["code"] == "claim_type_invalid" for error in details["validation_errors"])


def test_non_factual_with_support_status_is_cleared() -> None:
    score, details, _ = _score(
        [
            _claim(
                claim_type="non_factual",
                claim_subtype="absence",
                support_status="supported",
                evidence_refs=[],
            )
        ]
    )

    assert score is None
    assert details["claims"][0]["support_status"] is None
    assert any(
        error["code"] == "non_factual_support_status" for error in details["validation_errors"]
    )


def test_contradictory_without_pair_is_cleared() -> None:
    score, details, _ = _score(
        [
            _claim(
                support_status="unsupported",
                is_contradictory=True,
                contradiction_with=[],
                evidence_refs=[],
            )
        ]
    )

    assert score == 0.0
    assert details["claims"][0]["is_contradictory"] is False
    assert details["contradiction_count"] == 0
    assert any(
        error["code"] == "missing_contradiction_pair" for error in details["validation_errors"]
    )


def test_contradiction_with_non_factual_is_cleared() -> None:
    score, details, _ = _score(
        [
            _claim(
                claim_id="cl1",
                support_status="unsupported",
                is_contradictory=True,
                contradiction_with=["cl2"],
                evidence_refs=[],
            ),
            _claim(
                claim_id="cl2",
                claim_type="non_factual",
                claim_subtype="absence",
                support_status=None,
                evidence_refs=[],
            ),
        ]
    )

    assert score == 0.0
    assert details["claims"][0]["is_contradictory"] is False
    assert any(
        error["code"] == "non_factual_contradiction_pair" for error in details["validation_errors"]
    )


# --------------------------------------------------------------------------- v1 兼容


def test_v1_scoring_is_unchanged() -> None:
    score, details, reason = _score(
        [
            {"claim": "a", "supported": True, "evidence": ["ctx"], "reason": ""},
            {"claim": "b", "supported": False, "evidence": [], "reason": "无依据"},
        ],
        schema_version=JUDGE_SCHEMA_V1,
    )

    assert score == 0.5
    assert reason is None
    assert details["supported_count"] == 1
    assert details["claim_count"] == 2
    assert "validation_errors" not in details


def test_v1_no_claims_uses_no_claims_reason() -> None:
    score, details, reason = _score([], schema_version=JUDGE_SCHEMA_V1)

    assert score is None
    assert reason == "no_claims"
    assert details["claims"] == []


# --------------------------------------------------------------------------- 六案例 fixtures


def _load_acceptance() -> tuple[dict[str, Any], dict[str, Any]]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in matrix["cases"]}
    fixtures = {
        case["case_id"]: case
        for case in json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))["cases"]
    }
    return cases, fixtures


def _case_claims(case: dict[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for source in case["expected_claims"]:
        claims.append(
            {
                "claim_id": source["claim_id"],
                "claim": source["claim"],
                "claim_type": source["claim_type"],
                "claim_subtype": source.get("claim_subtype"),
                "support_status": source.get("support_status"),
                "is_contradictory": source.get("is_contradictory", False),
                "contradiction_with": list(source.get("contradiction_with") or []),
                "evidence_refs": [dict(item) for item in source.get("evidence_refs") or []],
                "reason": source.get("why", ""),
            }
        )
    return claims


def _case_score(
    case_id: str,
    mutate: Callable[[list[dict[str, Any]]], None] | None = None,
) -> tuple[float | None, dict[str, Any], str | None]:
    cases, fixtures = _load_acceptance()
    case = cases[case_id]
    fixture = fixtures[case["fixture_ref"]]
    claims = _case_claims(case)
    if mutate is not None:
        mutate(claims)
    return _faithfulness_score(
        {"claims": claims, "reason": "acceptance"},
        contexts=[item["content"] for item in fixture["answer_contexts"]],
        schema_version=JUDGE_SCHEMA_V2,
    )


def _by_id(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {claim["claim_id"]: claim for claim in claims}


@pytest.mark.parametrize(
    ("case_id", "expected_score", "expected_reason"),
    [
        ("Q23", 0.5, None),
        ("Q35", 1.0, None),
        ("Q36", 1.0, None),
        ("Q21#3", 0.6, None),
        ("Q11", 0.6, None),
        ("Q29", None, "no_scorable_claims"),
    ],
)
def test_acceptance_canonical_scores(
    case_id: str, expected_score: float | None, expected_reason: str | None
) -> None:
    score, details, reason = _case_score(case_id)

    assert score == pytest.approx(expected_score) if expected_score is not None else score is None
    assert reason == expected_reason
    if case_id == "Q23":
        assert details["contradiction_count"] == 1
    if case_id == "Q36":
        assert details["document_conflict"] is True
        assert details["document_conflict_count"] == 1
    if case_id == "Q21#3":
        assert details["insufficient_evidence_count"] == 2
    if case_id == "Q29":
        assert details["scorable_claim_count"] == 0


def test_acceptance_q35_wrong_context_downgrades() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        claim = _by_id(claims)["cl6"]
        claim["evidence_refs"] = [{"context_id": "C2", "quote": claim["evidence_refs"][0]["quote"]}]

    score, details, _ = _case_score("Q35", mutate)

    assert score == pytest.approx(5 / 6)
    assert details["evidence_validation_failed"] is True
    assert any(error["code"] == "quote_not_found" for error in details["validation_errors"])


def test_acceptance_q23_cl1_non_factual_changes_score() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        _by_id(claims)["cl1"].update(
            {
                "claim_type": "non_factual",
                "claim_subtype": "meta",
                "support_status": None,
                "is_contradictory": False,
                "contradiction_with": [],
                "evidence_refs": [],
            }
        )

    score, _, _ = _case_score("Q23", mutate)

    assert score == pytest.approx(3 / 5)
    assert not (0.4 <= score <= 0.5)


def test_acceptance_q21_supported_without_evidence_downgrades() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        claim = _by_id(claims)["cl4"]
        claim["support_status"] = "supported"
        claim["evidence_refs"] = []

    score, details, _ = _case_score("Q21#3", mutate)

    assert score == pytest.approx(3 / 5)
    assert details["evidence_validation_failed"] is True
    assert any(
        error["code"] == "supported_without_evidence" for error in details["validation_errors"]
    )


def test_acceptance_q21_all_supported_is_one() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        by_id = _by_id(claims)
        by_id["cl4"].update(
            {
                "support_status": "supported",
                "evidence_refs": [{"context_id": "C1", "quote": "质量问题需在签收后 24 小时内拍照反馈。"}],
            }
        )
        by_id["cl5"].update(
            {
                "support_status": "supported",
                "evidence_refs": [{"context_id": "C1", "quote": "电子产品自签收之日起保修 12 个月，配件保修 3 个月。"}],
            }
        )

    score, details, _ = _case_score("Q21#3", mutate)

    assert score == 1.0
    assert details["all_insufficient"] is False


def test_acceptance_q29_fabricated_claim_is_not_skipped() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        claims.append(
            {
                "claim_id": "cl4",
                "claim": "支持货到付款",
                "claim_type": "factual_claim",
                "claim_subtype": "policy",
                "support_status": "supported",
                "evidence_refs": [{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
                "is_contradictory": False,
                "contradiction_with": [],
            }
        )

    score, details, reason = _case_score("Q29", mutate)

    assert score == 1.0
    assert reason is None
    assert details["scorable_claim_count"] == 1


def test_acceptance_q36_conflict_marked_contradictory() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        claim = _by_id(claims)["cl8"]
        claim["is_contradictory"] = True
        claim["contradiction_with"] = ["cl1"]

    score, details, _ = _case_score("Q36", mutate)

    assert score == 1.0
    assert details["claims"][-1]["is_contradictory"] is False
    assert details["contradiction_count"] == 0
    assert any(
        error["code"] == "conflict_marked_contradictory" for error in details["validation_errors"]
    )


def test_acceptance_q23_contradictory_without_pair() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        _by_id(claims)["cl1"]["contradiction_with"] = []

    score, details, _ = _case_score("Q23", mutate)

    assert score == 0.5
    assert details["contradiction_count"] == 0
    assert any(
        error["code"] == "missing_contradiction_pair" for error in details["validation_errors"]
    )


def test_acceptance_q36_single_sided_evidence() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        claim = _by_id(claims)["cl8"]
        claim["evidence_refs"] = claim["evidence_refs"][:1]

    score, details, _ = _case_score("Q36", mutate)

    assert score == pytest.approx(7 / 8)
    assert details["document_conflict"] is False
    assert any(
        error["code"] == "conflict_single_sided_evidence" for error in details["validation_errors"]
    )


def test_acceptance_q11_cl4_excluded_as_non_factual() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        _by_id(claims)["cl4"].update(
            {
                "claim_type": "non_factual",
                "claim_subtype": "absence",
                "support_status": None,
                "evidence_refs": [],
            }
        )

    score, details, _ = _case_score("Q11", mutate)

    assert score == pytest.approx(3 / 4)
    assert details["scorable_claim_count"] == 4


def test_q11_target_range_accepts_five_of_six() -> None:
    cases, _ = _load_acceptance()
    text = cases["Q11"]["expected_scores"]["faithfulness"]
    match = re.search(r"target_range=(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", text)

    assert match is not None
    low, high = float(match.group(1)), float(match.group(2))
    assert low <= 5 / 6 <= high


def test_acceptance_q35_cl5_marked_supported() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        _by_id(claims)["cl5"]["support_status"] = "supported"

    score, details, _ = _case_score("Q35", mutate)

    assert score == 1.0
    assert details["claims"][4]["support_status"] is None
    assert any(
        error["code"] == "non_factual_support_status" for error in details["validation_errors"]
    )


def test_acceptance_q21_alternative_split_0667() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        keep = {"cl1", "cl2", "cl4", "cl6"}
        claims[:] = [claim for claim in claims if claim["claim_id"] in keep]

    score, details, _ = _case_score("Q21#3", mutate)

    assert score == pytest.approx(2 / 3)
    assert 0.6 <= score <= 0.7
    assert details["scorable_claim_count"] == 3


def test_acceptance_q36_base_without_cl8() -> None:
    def mutate(claims: list[dict[str, Any]]) -> None:
        claims[:] = [claim for claim in claims if claim["claim_id"] != "cl8"]

    score, details, _ = _case_score("Q36", mutate)

    assert score == 1.0
    assert details["scorable_claim_count"] == 7
    assert details["document_conflict"] is False


# --------------------------------------------------------------------------- 编排/版本接线


class _StubAgentV2:
    def __init__(
        self,
        metric: str,
        data: dict[str, Any] | None,
        *,
        success: bool = True,
        errors: list[str] | None = None,
        raw_text: str | None = "{}",
        original_raw_text: str | None = None,
    ) -> None:
        self.config = SimpleNamespace(
            name=f"rag_judge_{metric}",
            version="v1.1.1",
            temperature=0.0,
            max_tokens=512,
        )
        self.prompt_version = "v1.1.1"
        self.schema_version = JUDGE_SCHEMA_V2
        self.rubric_version = "v1.1.1"
        self.metric_version = "v2"
        self.prompt_sha256 = "a" * 64
        self._result = AgentResult(
            success=success,
            data=data,
            errors=list(errors or []),
            metadata={"model": "stub-judge-model"},
            raw_text=raw_text,
            original_raw_text=original_raw_text,
        )

    async def judge(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return self._result


def _trace(**overrides: Any) -> RagTrace:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "adapter": "mock",
        "mode": "query",
        "context_source": "agent_chat",
        "query": "q",
        "answer": "a",
        "status": "success",
        "retrieved_contexts": [
            {"content": "订单签收后 7 天内可申请无理由退款。"},
            {"content": "质量问题需在签收后 24 小时内拍照反馈。"},
        ],
    }
    values.update(overrides)
    return RagTrace(**values)


async def test_judge_trace_v2_skips_all_non_factual() -> None:
    cases, fixtures = _load_acceptance()
    claims = _case_claims(cases["Q29"])
    stub = _StubAgentV2("faithfulness", {"claims": claims, "reason": "q29"})

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["faithfulness"],
        agent_factory=lambda metric: stub,
        prompt_version="v1.1.1",
    )

    outcome = outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skipped_reason == "no_scorable_claims"
    assert outcome.metric_version == "v2"
    assert outcome.details["scorable_claim_count"] == 0
    assert outcome.judge_config["schema_version"] == JUDGE_SCHEMA_V2


async def test_judge_trace_v2_scores_q21() -> None:
    cases, fixtures = _load_acceptance()
    claims = _case_claims(cases["Q21#3"])
    contexts = [{"content": item["content"]} for item in fixtures["Q21"]["answer_contexts"]]
    stub = _StubAgentV2("faithfulness", {"claims": claims, "reason": "q21"})

    outcomes = await judge_trace(
        None,
        trace=_trace(retrieved_contexts=contexts),
        metrics=["faithfulness"],
        agent_factory=lambda metric: stub,
        prompt_version="v1.1.1",
    )

    outcome = outcomes[0]
    assert outcome.status == "evaluated"
    assert outcome.score == pytest.approx(0.6)
    assert outcome.metric_version == "v2"
    assert outcome.details["insufficient_evidence_count"] == 2
    assert outcome.details["all_insufficient"] is False


async def test_judge_trace_v2_skip_uses_v2_metric_version() -> None:
    outcomes = await judge_trace(
        None,
        trace=_trace(context_source="none", retrieved_contexts=[]),
        metrics=["faithfulness"],
        prompt_version="v1.1.1",
    )

    outcome = outcomes[0]
    assert outcome.status == "skipped"
    assert outcome.skipped_reason == "context_unavailable"
    assert outcome.metric_version == "v2"
    assert outcome.judge_config["schema_version"] == JUDGE_SCHEMA_V2


async def test_failed_outcome_keeps_original_and_final_raw_output() -> None:
    stub = _StubAgentV2(
        "faithfulness",
        None,
        success=False,
        errors=["StructuredOutputError: still invalid"],
        raw_text="final-repair-output",
        original_raw_text="first-invalid-output",
    )

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["faithfulness"],
        agent_factory=lambda metric: stub,
        prompt_version="v1.1.1",
    )

    outcome = outcomes[0]
    assert outcome.status == "failed"
    assert outcome.raw_output == "final-repair-output"
    assert outcome.details["original_raw_output"] == "first-invalid-output"


def test_metric_version_for_prompt_version() -> None:
    assert metric_version_for("faithfulness") == "v1"
    assert metric_version_for("faithfulness", "v1.0.0") == "v1"
    assert metric_version_for("faithfulness", "v1.1.1") == "v2"
    assert metric_version_for("hit_rate", "v1.1.1") == "v1"


def test_build_judge_config_defaults_to_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    config = build_judge_config(["faithfulness"])

    assert config["prompt_version"] == "v1.0.0"
    assert config["metric_versions"]["faithfulness"] == "v1"
    assert config["metric_fingerprints"]["faithfulness"]["schema_version"] == JUDGE_SCHEMA_V1


def test_build_judge_config_v111_uses_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.1.1")

    config = build_judge_config(["faithfulness"])

    assert config["prompt_version"] == "v1.1.1"
    assert config["metric_versions"]["faithfulness"] == "v2"
    fingerprint = config["metric_fingerprints"]["faithfulness"]
    assert fingerprint["schema_version"] == JUDGE_SCHEMA_V2
    assert fingerprint["rubric_version"] == "v1.1.1"
    assert fingerprint["resolved_prompt_version"] == "v1.1.1"


def test_build_aggregate_uses_run_prompt_version() -> None:
    run = SimpleNamespace(
        total_items=1,
        config_snapshot={"metrics": [], "judge_metrics": ["faithfulness"]},
        dataset_id=None,
        dataset_name="d",
        dataset_version_id="v1",
        execution_mode="query",
        adapter="mock",
        completed_items=1,
        failed_items=0,
        skipped_items=0,
        judge_config={"prompt_version": "v1.1.1"},
    )
    result = RagEvaluationResult(
        run_id=uuid.uuid4(),
        dataset_item_id=uuid.uuid4(),
        metric_name="faithfulness",
        metric_version="v2",
        status="evaluated",
        score=0.6,
        details={},
        judge_config={},
    )

    aggregate = build_aggregate(run, [result], unprocessed_items=0)

    assert aggregate["metrics"]["faithfulness"]["metric_version"] == "v2"
    assert aggregate["metrics"]["faithfulness"]["mean"] == pytest.approx(0.6)
