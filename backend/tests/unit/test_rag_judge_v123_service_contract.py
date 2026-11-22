"""v1.2.3 Service shared-validator, golden regression, and agent_contract tests."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.base import AgentConfig, AgentResult
from app.agents.rag_judge_agent import RagJudgeAgent
from app.core.llm import LLMResponse, LLMUsage
from app.models import RagTrace
from app.schemas.agents.rag_judge import (
    JUDGE_SCHEMA_V2,
    JUDGE_SCHEMA_V3,
)
from app.schemas.agents.rag_judge_evidence import (
    build_context_map,
    check_quote,
)
from app.services.rag_judge_service import (
    _agent_contract_details,
    _faithfulness_score,
    _faithfulness_score_v3,
    _judge_config,
    judge_trace,
)

pytestmark = pytest.mark.unit

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
Q23_RAW = json.loads((FIXTURE_DIR / "rag_judge_q23_v122_raw.json").read_text(encoding="utf-8"))
Q23_CONTEXTS = json.loads((FIXTURE_DIR / "rag_judge_q23_contexts.json").read_text(encoding="utf-8"))


def test_q23_golden_raw_output_still_invalid_with_same_quote_errors() -> None:
    coverage, strict = _faithfulness_score_v3(Q23_RAW, contexts=Q23_CONTEXTS)

    assert coverage.status == "invalid"
    assert coverage.invalid_reason == "contract_violation"
    assert strict.status == "invalid"
    errors = coverage.details["validation_errors"]
    assert [error["claim_id"] for error in errors] == ["cl1", "cl2", "cl3"]
    assert [error["code"] for error in errors] == ["quote_not_found"] * 3
    assert coverage.details["claim_count"] == 10
    assert coverage.details["supported_count"] == 3
    assert coverage.details["insufficient_evidence_count"] == 3
    assert coverage.details["non_factual_count"] == 4


def test_service_quote_checks_match_shared_validator() -> None:
    coverage, _ = _faithfulness_score_v3(Q23_RAW, contexts=Q23_CONTEXTS)
    context_map = build_context_map(Q23_CONTEXTS)
    expected = []
    for claim in Q23_RAW["claims"]:
        for ref in claim.get("evidence_refs") or []:
            expected.append(
                check_quote(
                    quote=ref["quote"],
                    context_id=ref["context_id"],
                    context_map=context_map,
                    claim_id=claim["claim_id"],
                )
            )

    actual = coverage.details["evidence_validation"]
    assert len(actual) == len(expected)
    for actual_row, expected_check in zip(actual, expected, strict=True):
        assert actual_row["claim_id"] == expected_check.claim_id
        assert actual_row["context_id"] == expected_check.context_id
        assert actual_row["ok"] == expected_check.ok
        assert actual_row["error"] == expected_check.error


def test_v2_quote_path_is_unchanged() -> None:
    data = {
        "claims": [
            {
                "claim_id": "cl1",
                "claim": "退款 1-3 天到账",
                "claim_type": "factual_claim",
                "claim_subtype": "policy",
                "support_status": "supported",
                "is_contradictory": False,
                "contradiction_with": [],
                "evidence_refs": [{"context_id": "C1", "quote": "不存在的句子"}],
                "reason": "",
            }
        ],
        "reason": "",
    }

    score, details, skipped = _faithfulness_score(
        data,
        contexts=["退款 1-3 天到账。"],
        schema_version=JUDGE_SCHEMA_V2,
    )

    assert score == 0.0
    assert skipped is None
    assert details["validation_errors"][0]["code"] == "quote_not_found"


def test_judge_config_contract_fields_are_version_gated() -> None:
    old = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.2")
    new = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.3")

    old_config = _judge_config(old, model=None)
    new_config = _judge_config(new, model=None)

    assert "contract_repair_version" not in old_config
    assert "quote_validator_sha256" not in old_config
    assert new_config["contract_repair_version"] == "v1.2.3"
    assert len(new_config["quote_validator_sha256"]) == 64


class ContractStubAgent:
    def __init__(
        self,
        *,
        success: bool,
        data: dict[str, Any] | None = None,
        contract_report: dict[str, Any] | None = None,
    ) -> None:
        self.metric_version = "v3"
        self.schema_version = JUDGE_SCHEMA_V3
        self.rubric_version = "v1.2.0"
        self.prompt_sha256 = "a" * 64
        self.contract_repair_version = "v1.2.3"
        self.quote_validator_sha256 = "b" * 64
        self.contract_report = contract_report
        self.config = SimpleNamespace(
            name="rag_judge_faithfulness",
            version="v1.2.3",
            temperature=0.0,
            max_tokens=8192,
        )
        self._result = AgentResult(
            success=success,
            data=data,
            errors=[] if success else ["structured output is still invalid"],
            metadata={"model": "stub-judge-model"},
            raw_text="raw",
        )
        if not success:
            self._result.error_type = "StructuredOutputError"

    async def judge(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        return self._result


def _trace() -> RagTrace:
    return RagTrace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        adapter="fixture",
        mode="query",
        context_source="agent_chat",
        query="q",
        answer="a",
        status="success",
        retrieved_contexts=[{"content": "退款 1-3 天到账。"}],
    )


async def test_invalid_contract_outcome_carries_agent_contract() -> None:
    report = {
        "contract_version": "v1.2.3",
        "quote_precheck_errors": [{"claim_id": "cl1", "code": "quote_not_found"}],
        "repair_triggered": True,
        "repair_count": 1,
        "passed_after_repair": False,
        "final_errors": [{"claim_id": "cl1", "code": "quote_not_found"}],
        "mixed_sentence_warnings": [],
    }
    stub = ContractStubAgent(success=False, contract_report=report)

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["faithfulness"],
        agent_factory=lambda metric: stub,
    )

    faith = next(row for row in outcomes if row.metric_name == "faithfulness")
    assert faith.status == "invalid"
    assert faith.details["agent_contract"]["passed_after_repair"] is False
    assert faith.details["agent_contract"]["final_errors"]


async def test_successful_contract_outcome_carries_agent_contract() -> None:
    report = {
        "contract_version": "v1.2.3",
        "quote_precheck_errors": [],
        "repair_triggered": False,
        "repair_count": 0,
        "passed_after_repair": True,
        "mixed_sentence_warnings": [{"claim_id": "cl2", "code": "mixed_sentence"}],
        "final_errors": [],
    }
    data = {
        "claims": [
            {
                "claim_id": "cl1",
                "claim": "退款 1-3 天到账",
                "claim_type": "factual_claim",
                "claim_subtype": "policy",
                "support_status": "supported",
                "evidence_refs": [{"context_id": "C1", "quote": "退款 1-3 天到账。"}],
            }
        ],
        "reason": "",
    }
    stub = ContractStubAgent(success=True, data=data, contract_report=report)

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["faithfulness"],
        agent_factory=lambda metric: stub,
    )

    faith = next(row for row in outcomes if row.metric_name == "faithfulness")
    strict = next(row for row in outcomes if row.metric_name == "faithfulness_strict")
    assert faith.status == "evaluated"
    assert faith.details["agent_contract"]["repair_triggered"] is False
    assert faith.details["agent_contract"]["mixed_sentence_warnings"]
    assert strict.details["agent_contract"]["repair_triggered"] is False


class RepairFailLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        self.calls += 1
        return LLMResponse(
            content=self.content,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="fake-judge-model",
            latency_ms=1.0,
        )


async def test_real_agent_repair_failure_invalid_carries_agent_contract() -> None:
    raw = json.dumps(Q23_RAW, ensure_ascii=False)
    llm = RepairFailLLM(raw)
    agent = RagJudgeAgent(
        "faithfulness",
        config=AgentConfig(
            name="rag_judge_faithfulness",
            version="v1.2.3",
            max_retries=0,
            timeout=5.0,
            max_tokens=512,
        ),
        llm=llm,
        prompt_version="v1.2.3",
    )
    trace = RagTrace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        adapter="fixture",
        mode="query",
        context_source="agent_chat",
        query="q",
        answer="a",
        status="success",
        retrieved_contexts=[{"content": item} for item in Q23_CONTEXTS],
    )

    outcomes = await judge_trace(
        None,
        trace=trace,
        metrics=["faithfulness"],
        agent_factory=lambda metric: agent,
    )

    faith = next(row for row in outcomes if row.metric_name == "faithfulness")
    strict = next(row for row in outcomes if row.metric_name == "faithfulness_strict")
    assert llm.calls == 2
    assert faith.status == "invalid"
    report = faith.details["agent_contract"]
    assert report["repair_triggered"] is True
    assert report["repair_count"] == 1
    assert report["passed_after_repair"] is False
    assert report["final_errors"]
    assert strict.details["agent_contract"]["passed_after_repair"] is False


def test_agent_contract_details_are_bounded() -> None:
    report = {
        "contract_version": "v1.2.3",
        "quote_precheck_errors": [
            {
                "claim_id": f"cl{index}",
                "code": "quote_not_found",
                "quote": "q" * 500,
                "context_excerpt": "c" * 500,
            }
            for index in range(5)
        ],
        "mixed_sentence_warnings": [
            {"claim_id": f"cl{index}", "claim": "x" * 500} for index in range(5)
        ],
        "final_errors": [{"claim_id": f"cl{index}", "quote": "z" * 500} for index in range(5)],
    }

    details = _agent_contract_details(SimpleNamespace(contract_report=report))
    encoded = json.dumps(details, ensure_ascii=False)

    assert len(encoded) <= 2000
    assert details["agent_contract"]["quote_precheck_errors"]
