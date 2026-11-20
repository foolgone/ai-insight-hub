"""C3：v3 双指标、invalid、Item 聚合与 retry 候选规则。"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.base import AgentResult
from app.core.exceptions import (
    LLMCredentialInvalidError,
    LLMCredentialNotConfiguredError,
)
from app.models import RagEvaluationResult
from app.schemas.agents.rag_judge import FAITHFULNESS_STRICT_METRIC, JUDGE_SCHEMA_V3
from app.services.rag_evaluation_runner import _strict_row_from_coverage
from app.services.rag_evaluation_service import (
    build_aggregate,
    expected_metrics,
    item_bucket,
    retry_candidates,
)
from app.services.rag_judge_service import (
    _failure_fields,
    _faithfulness_score_v3,
    judge_trace,
)

pytestmark = pytest.mark.unit

CONTEXTS = ["订单签收后 7 天内可申请无理由退款。", "质量问题需在签收后 24 小时内拍照反馈。"]


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


def _result(
    status: str,
    *,
    metric: str = "faithfulness",
    score: float | None = None,
    invalid_reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> RagEvaluationResult:
    return RagEvaluationResult(
        run_id=uuid.uuid4(),
        dataset_item_id=uuid.uuid4(),
        metric_name=metric,
        metric_version="v3",
        status=status,
        score=score,
        invalid_reason=invalid_reason,
        details=details or {},
        judge_config={},
    )


# --------------------------------------------------------------------------- v3 scoring


def test_v3_coverage_and_strict_scoring() -> None:
    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                _claim(),
                _claim(
                    claim_id="cl2",
                    claim="质量问题需在签收后 24 小时内拍照反馈",
                    support_status="unsupported",
                    evidence_refs=[],
                ),
                _claim(
                    claim_id="cl3",
                    claim="定制类商品不支持无理由退款",
                    claim_subtype="condition",
                    support_status="insufficient_evidence",
                    evidence_refs=[],
                ),
                _claim(
                    claim_id="cl4",
                    claim="文档未提及海外配送",
                    claim_type="non_factual",
                    claim_subtype="absence",
                    support_status=None,
                    evidence_refs=[],
                ),
            ]
        },
        contexts=CONTEXTS,
    )

    assert coverage.status == "evaluated"
    assert coverage.score == pytest.approx(1 / 3, abs=1e-6)
    assert coverage.details["supported_count"] == 1
    assert coverage.details["unsupported_count"] == 1
    assert coverage.details["insufficient_evidence_count"] == 1
    assert coverage.details["non_factual_count"] == 1
    assert coverage.details["insufficient_ratio"] == pytest.approx(1 / 3, abs=1e-6)
    assert strict.status == "evaluated"
    assert strict.score == pytest.approx(0.5)
    assert "claims" not in strict.details


def test_v3_all_insufficient_boundary() -> None:
    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                _claim(
                    claim_id="cl1",
                    support_status="insufficient_evidence",
                    evidence_refs=[],
                ),
                _claim(
                    claim_id="cl2",
                    claim="质量问题需在签收后 24 小时内拍照反馈",
                    support_status="insufficient_evidence",
                    evidence_refs=[],
                ),
            ]
        },
        contexts=CONTEXTS,
    )

    assert coverage.status == "evaluated"
    assert coverage.score == 0.0
    assert coverage.details["all_insufficient"] is True
    assert coverage.details["insufficient_ratio"] == 1.0
    assert strict.status == "skipped"
    assert strict.skipped_reason == "no_decidable_claims"


def test_v3_contract_violation_is_invalid() -> None:
    coverage, strict = _faithfulness_score_v3(
        {"claims": [_claim(evidence_refs=[])]},
        contexts=CONTEXTS,
    )

    assert coverage.status == "invalid"
    assert coverage.invalid_reason == "contract_violation"
    assert strict.status == "invalid"
    assert strict.invalid_reason == "contract_violation"
    assert "claims" not in strict.details


# --------------------------------------------------------------------------- failure mapping


def test_error_type_mapping() -> None:
    assert _failure_fields("AgentOutputError") == ("invalid", "contract_violation", "contract")
    assert _failure_fields("StructuredOutputError") == (
        "invalid",
        "contract_violation",
        "contract",
    )
    assert _failure_fields("AgentInputError") == ("failed", None, "input_error")
    assert _failure_fields("AgentTimeoutError") == ("failed", None, "timeout")
    assert _failure_fields("AgentExecutionError") == ("failed", None, "execution")
    assert _failure_fields("AgentDegradedError") == ("failed", None, "execution")
    assert _failure_fields("LLMCredentialInvalidError") == (  # noqa: E501
        "failed",
        None,
        "credential",
    )
    assert _failure_fields("UnknownError") == ("failed", None, "unknown")


class _CredentialAgent:
    schema_version = JUDGE_SCHEMA_V3
    metric_version = "v3"
    rubric_version = "v1.2.0"
    prompt_sha256 = "a" * 64
    config = SimpleNamespace(
        name="rag_judge_faithfulness", temperature=0.0, max_tokens=100, version="v1.2.0"
    )

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def judge(self, input_data: Any, **kwargs: Any) -> AgentResult:
        raise self._exc


@pytest.mark.parametrize(
    "exc",
    [LLMCredentialNotConfiguredError(), LLMCredentialInvalidError()],
)
async def test_credential_failure_becomes_failed_outcome(exc: Exception) -> None:
    trace = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task_id=None,
        query="退款多久到账？",
        answer="7 天内可申请。",
        retrieved_contexts=[{"content": CONTEXTS[0]}],
        context_source="agent_chat",
        status="success",
    )
    agent = _CredentialAgent(exc)

    outcomes = await judge_trace(
        None,
        trace=trace,  # type: ignore[arg-type]
        metrics=["faithfulness"],
        agent_factory=lambda metric: agent,  # type: ignore[arg-type]
        prompt_version="v1.2.0",
        schema_version=JUDGE_SCHEMA_V3,
    )

    assert len(outcomes) == 2
    assert [item.metric_name for item in outcomes] == [
        "faithfulness",
        FAITHFULNESS_STRICT_METRIC,
    ]
    for outcome in outcomes:
        assert outcome.status == "failed"
        assert outcome.invalid_reason is None
        assert outcome.details["failure_kind"] == "credential"


class _ResultAgent:
    schema_version = JUDGE_SCHEMA_V3
    metric_version = "v3"
    rubric_version = "v1.2.0"
    prompt_sha256 = "a" * 64
    config = SimpleNamespace(
        name="rag_judge_faithfulness", temperature=0.0, max_tokens=100, version="v1.2.0"
    )

    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def judge(self, input_data: Any, **kwargs: Any) -> AgentResult:
        return self._result


def _trace() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        task_id=None,
        query="退款多久到账？",
        answer="7 天内可申请。",
        retrieved_contexts=[{"content": CONTEXTS[0]}],
        context_source="agent_chat",
        status="success",
    )


async def test_judge_trace_v3_success_returns_dual_outcomes() -> None:
    agent = _ResultAgent(
        AgentResult(success=True, data={"claims": [_claim()]}, metadata={"model": "fake"})
    )

    outcomes = await judge_trace(
        None,
        trace=_trace(),  # type: ignore[arg-type]
        metrics=["faithfulness"],
        agent_factory=lambda metric: agent,  # type: ignore[arg-type]
        prompt_version="v1.2.0",
        schema_version=JUDGE_SCHEMA_V3,
    )

    assert [item.metric_name for item in outcomes] == [
        "faithfulness",
        FAITHFULNESS_STRICT_METRIC,
    ]
    assert outcomes[0].status == "evaluated"
    assert outcomes[0].score == pytest.approx(1.0)
    assert outcomes[1].status == "evaluated"
    assert outcomes[1].score == pytest.approx(1.0)
    assert "claims" not in outcomes[1].details


async def test_judge_trace_v3_output_error_is_invalid() -> None:
    agent = _ResultAgent(
        AgentResult(
            success=False,
            errors=["AgentOutputError: schema invalid"],
            error_type="AgentOutputError",
        )
    )

    outcomes = await judge_trace(
        None,
        trace=_trace(),  # type: ignore[arg-type]
        metrics=["faithfulness"],
        agent_factory=lambda metric: agent,  # type: ignore[arg-type]
        prompt_version="v1.2.0",
        schema_version=JUDGE_SCHEMA_V3,
    )

    for outcome in outcomes:
        assert outcome.status == "invalid"
        assert outcome.invalid_reason == "contract_violation"


# --------------------------------------------------------------------------- expected/aggregate


def test_expected_metrics_includes_strict() -> None:
    run = SimpleNamespace(
        config_snapshot={
            "metrics": [],
            "judge_metrics": ["faithfulness"],
            "derived_metrics": [FAITHFULNESS_STRICT_METRIC],
        },
        judge_config={"prompt_version": "v1.2.0"},
    )
    assert expected_metrics(run) == ["faithfulness", FAITHFULNESS_STRICT_METRIC]


def test_expected_metrics_falls_back_for_old_v3_snapshot() -> None:
    run = SimpleNamespace(
        config_snapshot={"metrics": [], "judge_metrics": ["faithfulness"]},
        judge_config={"prompt_version": "v1.2.0"},
    )
    assert expected_metrics(run) == ["faithfulness", FAITHFULNESS_STRICT_METRIC]


def test_expected_metrics_v2_has_no_strict() -> None:
    run = SimpleNamespace(
        config_snapshot={"metrics": [], "judge_metrics": ["faithfulness"]},
        judge_config={"prompt_version": "v1.1.5"},
    )
    assert expected_metrics(run) == ["faithfulness"]


def test_retry_parent_missing_prompt_rejected() -> None:
    from app.core.exceptions import RagEvaluationConflictError
    from app.services.rag_evaluation_service import _assert_parent_snapshot_available

    parent = SimpleNamespace(
        config_snapshot={"judge_metrics": ["faithfulness"]},
        judge_config={"prompt_version": "v1.2.0"},
    )
    with pytest.raises(RagEvaluationConflictError, match="父快照不可用"):
        _assert_parent_snapshot_available(parent)  # type: ignore[arg-type]


def test_item_bucket_priorities() -> None:
    evaluated = _result("evaluated", score=1.0)
    invalid = _result("invalid", invalid_reason="contract_violation")
    failed = _result("failed")
    skipped = _result("skipped")
    b_invalid = _result("failed", invalid_reason="contract_violation")

    assert item_bucket([evaluated, invalid]) == "invalid"
    assert item_bucket([evaluated, failed]) == "failed"
    assert item_bucket([evaluated, b_invalid]) == "invalid"
    assert item_bucket([evaluated, skipped]) == "evaluated"
    assert item_bucket([skipped]) == "skipped"
    assert item_bucket([failed, invalid]) == "failed"


def test_retry_candidates_exclude_item_with_any_invalid() -> None:
    item_ok = uuid.uuid4()
    item_failed = uuid.uuid4()
    item_invalid = uuid.uuid4()
    item_strict_missing = uuid.uuid4()

    state = {
        item_ok: {
            "faithfulness": _result("evaluated", score=1.0),
            FAITHFULNESS_STRICT_METRIC: _result(
                "evaluated", metric=FAITHFULNESS_STRICT_METRIC, score=1.0
            ),
        },
        item_failed: {"faithfulness": _result("failed")},
        item_invalid: {
            "faithfulness": _result("evaluated", score=1.0),
            FAITHFULNESS_STRICT_METRIC: _result(
                "invalid",
                metric=FAITHFULNESS_STRICT_METRIC,
                invalid_reason="contract_violation",
            ),
        },
        item_strict_missing: {"faithfulness": _result("evaluated", score=1.0)},
    }
    expected = ["faithfulness", FAITHFULNESS_STRICT_METRIC]
    versions = {metric: "v3" for metric in expected}

    candidates = retry_candidates(
        all_ids={item_ok, item_failed, item_invalid, item_strict_missing},
        expected=expected,
        expected_versions=versions,
        state=state,
    )

    assert set(candidates) == {item_failed, item_strict_missing}


def test_build_aggregate_invalid_and_insufficient() -> None:
    run = SimpleNamespace(
        total_items=2,
        config_snapshot={
            "metrics": [],
            "judge_metrics": ["faithfulness"],
            "derived_metrics": [FAITHFULNESS_STRICT_METRIC],
        },
        judge_config={"prompt_version": "v1.2.0"},
        dataset_id=None,
        dataset_name="d",
        dataset_version_id="v1",
        execution_mode="query",
        adapter="mock",
        completed_items=1,
        evaluated_items=1,
        invalid_items=1,
        failed_items=0,
        skipped_items=0,
    )
    results = [
        _result(
            "evaluated",
            score=0.6,
            details={
                "supported_count": 3,
                "unsupported_count": 0,
                "insufficient_evidence_count": 2,
                "all_insufficient": False,
            },
        ),
        _result(
            "evaluated",
            metric=FAITHFULNESS_STRICT_METRIC,
            score=1.0,
            details={"supported_count": 3, "unsupported_count": 0},
        ),
        _result("invalid", invalid_reason="contract_violation"),
        _result(
            "invalid",
            metric=FAITHFULNESS_STRICT_METRIC,
            invalid_reason="contract_violation",
        ),
    ]

    aggregate = build_aggregate(run, results, unprocessed_items=0)

    faith = aggregate["metrics"]["faithfulness"]
    assert faith["mean"] == pytest.approx(0.6)
    assert faith["insufficient_count"] == 2
    assert faith["insufficient_ratio"] == pytest.approx(0.4)
    assert faith["invalid"] == 1
    strict = aggregate["metrics"][FAITHFULNESS_STRICT_METRIC]
    assert strict["mean"] == pytest.approx(1.0)
    assert strict["invalid"] == 1
    assert aggregate["items"]["evaluated"] == 1
    assert aggregate["items"]["invalid"] == 1
    assert aggregate["items"]["processed"] == 2


def test_strict_row_for_all_insufficient_is_skipped() -> None:
    coverage = _result(
        "evaluated",
        score=0.0,
        details={
            "claims": [{"claim": "x"}],
            "supported_count": 0,
            "unsupported_count": 0,
            "insufficient_evidence_count": 3,
            "all_insufficient": True,
        },
    )
    run = SimpleNamespace(id=coverage.run_id)
    item = SimpleNamespace(id=coverage.dataset_item_id)

    strict = _strict_row_from_coverage(
        run=run,  # type: ignore[arg-type]
        item=item,  # type: ignore[arg-type]
        coverage=coverage,
    )

    assert strict.status == "skipped"
    assert strict.skipped_reason == "no_decidable_claims"
    assert strict.derived_from_result_id == coverage.id


def test_strict_row_from_coverage_has_no_heavy_details() -> None:
    coverage = _result(
        "evaluated",
        score=0.6,
        details={
            "claims": [{"claim": "x"}],
            "supported_count": 3,
            "unsupported_count": 0,
            "insufficient_evidence_count": 2,
            "all_insufficient": False,
        },
    )
    run = SimpleNamespace(id=coverage.run_id)
    item = SimpleNamespace(id=coverage.dataset_item_id)

    strict = _strict_row_from_coverage(
        run=run,  # type: ignore[arg-type]
        item=item,  # type: ignore[arg-type]
        coverage=coverage,
    )

    assert strict.metric_name == FAITHFULNESS_STRICT_METRIC
    assert strict.status == "evaluated"
    assert strict.score == pytest.approx(1.0)
    assert strict.derived_from_result_id == coverage.id
    assert "claims" not in strict.details
    assert strict.details["strict_score"] == pytest.approx(1.0)
