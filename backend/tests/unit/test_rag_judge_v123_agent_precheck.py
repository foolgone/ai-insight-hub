"""v1.2.3 Agent quote precheck + targeted repair tests (no real LLM)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.base import AgentConfig, neutralize_payload
from app.agents.rag_judge_agent import RagJudgeAgent
from app.core.llm import LLMResponse, LLMUsage
from app.schemas.agents.rag_judge import FaithfulnessOutputV3, RagJudgeInput
from app.schemas.agents.rag_judge_evidence import QuoteContractError

pytestmark = pytest.mark.unit

CONTEXT = "商品签收后不支持无理由退货；出现质量问题的，需在签收后 24 小时内提交照片反馈。"
TRUNCATED = "商品出现质量问题时可在 24 小时内反馈。"
CONTIGUOUS = "出现质量问题的，需在签收后 24 小时内提交照片反馈。"


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.last_messages: list[object] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        self.last_messages = list(messages)
        item = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return LLMResponse(
            content=item,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="fake-judge-model",
            latency_ms=1.0,
        )


def _agent(metric: str, responses: list[str], version: str = "v1.2.3"):
    llm = FakeLLM(responses)
    agent = RagJudgeAgent(
        metric,  # type: ignore[arg-type]
        config=AgentConfig(
            name=f"rag_judge_{metric}",
            version=version,
            max_retries=0,
            timeout=5.0,
            max_tokens=512,
        ),
        llm=llm,
        prompt_version=version,
    )
    return agent, llm


def _payload() -> dict[str, object]:
    return {
        "query": "商品出现质量问题还能反馈吗？",
        "answer": TRUNCATED,
        "contexts": [CONTEXT],
    }


def _claim_json(
    *,
    claim: str,
    quote: str,
    claim_type: str = "factual_claim",
    subtype: str = "policy",
    support: str | None = "supported",
    refs: list[dict[str, str]] | None = None,
) -> str:
    claim_payload: dict[str, object] = {
        "claim_id": "cl1",
        "claim": claim,
        "claim_type": claim_type,
        "claim_subtype": subtype,
        "support_status": support,
        "is_contradictory": False,
        "contradiction_with": [],
        "evidence_refs": refs
        if refs is not None
        else ([{"context_id": "C1", "quote": quote}] if quote else []),
        "reason": "test",
    }
    return json.dumps({"claims": [claim_payload], "reason": ""}, ensure_ascii=False)


VALID_REPAIRED = _claim_json(
    claim="出现质量问题的，需在签收后 24 小时内提交照片反馈",
    quote=CONTIGUOUS,
)
INVALID_TRUNCATED = _claim_json(
    claim="商品出现质量问题时可在 24 小时内反馈",
    quote=TRUNCATED,
)


async def test_v123_truncated_quote_triggers_repair_and_passes() -> None:
    agent, llm = _agent("faithfulness", [INVALID_TRUNCATED, VALID_REPAIRED])

    result = await agent.judge(_payload())

    assert result.success is True
    assert llm.calls == 2
    assert result.raw_text == VALID_REPAIRED
    report = agent.contract_report or {}
    assert report["repair_triggered"] is True
    assert report["repair_count"] == 1
    assert report["passed_after_repair"] is True
    assert report["quote_precheck_errors"][0]["code"] == "quote_not_found"
    assert "quote_not_found" in str(llm.last_messages)
    assert "context_excerpt" in str(llm.last_messages)


async def test_v123_truncated_quote_twice_still_fails_with_contract_report() -> None:
    agent, llm = _agent("faithfulness", [INVALID_TRUNCATED, INVALID_TRUNCATED])

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    assert result.error_type == "StructuredOutputError"
    report = agent.contract_report or {}
    assert report["repair_triggered"] is True
    assert report["repair_count"] == 1
    assert report["passed_after_repair"] is False
    assert report["final_errors"]


async def test_v122_does_not_run_quote_precheck() -> None:
    agent, llm = _agent("faithfulness", [INVALID_TRUNCATED], version="v1.2.2")

    result = await agent.judge(_payload())

    assert result.success is True
    assert llm.calls == 1
    assert agent.contract_report is None


async def test_v123_supported_mixed_sentence_triggers_repair() -> None:
    mixed = _claim_json(
        claim="该时限是硬性要求，文档未提及例外情形",
        quote=CONTIGUOUS,
        subtype="policy_scope",
    )
    repaired = json.dumps(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "该时限是硬性要求",
                    "claim_type": "factual_claim",
                    "claim_subtype": "policy_scope",
                    "support_status": "insufficient_evidence",
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "evidence_refs": [],
                    "reason": "无直接依据",
                },
                {
                    "claim_id": "cl2",
                    "claim": "文档未提及例外情形",
                    "claim_type": "non_factual",
                    "claim_subtype": "absence",
                    "support_status": None,
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "evidence_refs": [],
                    "reason": "absence",
                },
            ],
            "reason": "",
        },
        ensure_ascii=False,
    )
    agent, llm = _agent("faithfulness", [mixed, repaired])

    result = await agent.judge(_payload())

    assert result.success is True
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["repair_triggered"] is True
    assert any(
        error["code"] == "mixed_sentence_factual_absence"
        for error in report["quote_precheck_errors"]
    )


async def test_v123_insufficient_mixed_sentence_is_warning_only() -> None:
    mixed = _claim_json(
        claim="该时限是硬性要求，文档未提及例外情形",
        quote="",
        subtype="policy_scope",
        support="insufficient_evidence",
        refs=[],
    )
    agent, llm = _agent("faithfulness", [mixed])

    result = await agent.judge(_payload())

    assert result.success is True
    assert llm.calls == 1
    report = agent.contract_report or {}
    assert report["repair_triggered"] is False
    assert report["passed_after_repair"] is True
    assert report["mixed_sentence_warnings"]


async def test_v123_non_faithfulness_has_no_contract_report() -> None:
    agent, _ = _agent(
        "answer_relevancy",
        [json.dumps({"score": 0.9, "reason": "ok"})],
    )

    result = await agent.judge({"query": "q", "answer": "a"})

    assert result.success is True
    assert agent.contract_report is None


def test_v123_q23_real_raw_output_triggers_quote_and_mixed_errors() -> None:
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
    raw = json.loads((fixture_dir / "rag_judge_q23_v122_raw.json").read_text(encoding="utf-8"))
    contexts = json.loads((fixture_dir / "rag_judge_q23_contexts.json").read_text(encoding="utf-8"))
    agent, _ = _agent("faithfulness", [json.dumps(raw, ensure_ascii=False)])
    agent._active_input = RagJudgeInput(
        query="q",
        answer="a",
        contexts=contexts,
    )

    with pytest.raises(QuoteContractError) as excinfo:
        agent._validate_parsed(FaithfulnessOutputV3.model_validate(raw))

    message = str(excinfo.value)
    report = agent.contract_report or {}
    assert "quote_not_found" in message
    assert [error["claim_id"] for error in report["quote_precheck_errors"][:3]] == [
        "cl1",
        "cl2",
        "cl3",
    ]
    assert any(warning["claim_id"] == "cl5" for warning in report["mixed_sentence_warnings"])


def test_fixture_contexts_are_not_rewritten_by_neutralize_payload() -> None:
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
    contexts = json.loads((fixture_dir / "rag_judge_q23_contexts.json").read_text(encoding="utf-8"))

    sanitized, hits = neutralize_payload({"contexts": contexts})

    assert hits == []
    assert sanitized["contexts"] == contexts
