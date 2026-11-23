"""v1.2.4 evidence-only patch repair tests."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.agents.base import AgentConfig
from app.agents.rag_judge_agent import RagJudgeAgent
from app.core.llm import LLMResponse, LLMUsage
from app.models import RagTrace
from app.schemas.agents.rag_judge import FaithfulnessOutputV3
from app.services.rag_judge_service import _faithfulness_score_v3, judge_trace

pytestmark = pytest.mark.unit

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
Q23_RAW = json.loads((FIXTURE_DIR / "rag_judge_q23_v122_raw.json").read_text(encoding="utf-8"))
Q23_CONTEXTS = json.loads((FIXTURE_DIR / "rag_judge_q23_contexts.json").read_text(encoding="utf-8"))
FIXED_QUOTE = "质量问题需在签收后 24 小时内拍照反馈"
PATCH_OK = {
    "fixes": [
        {
            "claim_id": "cl1",
            "evidence_refs": [{"context_id": "C1", "quote": FIXED_QUOTE}],
        },
        {
            "claim_id": "cl2",
            "evidence_refs": [{"context_id": "C1", "quote": FIXED_QUOTE}],
        },
        {
            "claim_id": "cl3",
            "evidence_refs": [{"context_id": "C1", "quote": FIXED_QUOTE}],
        },
    ]
}


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        item = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return LLMResponse(
            content=item,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="fake-judge-model",
            latency_ms=1.0,
        )


def _agent(metric: str, responses: list[str], version: str = "v1.2.4"):
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


def _payload(contexts: list[str] | None = None) -> dict[str, object]:
    return {
        "query": "q",
        "answer": "answer",
        "contexts": contexts or Q23_CONTEXTS,
    }


async def test_v124_patch_fixes_only_evidence_and_keeps_cl1_supported() -> None:
    agent, llm = _agent(
        "faithfulness",
        [json.dumps(Q23_RAW, ensure_ascii=False), json.dumps(PATCH_OK, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is True
    assert llm.calls == 2
    data = result.data or {}
    output = FaithfulnessOutputV3.model_validate(data)
    by_id = {claim.claim_id: claim for claim in output.claims}
    assert by_id["cl1"].support_status == "supported"
    assert by_id["cl2"].evidence_refs[0].quote == FIXED_QUOTE
    assert by_id["cl3"].evidence_refs[0].quote == FIXED_QUOTE
    coverage, _ = _faithfulness_score_v3(data, contexts=Q23_CONTEXTS)
    assert coverage.status == "evaluated"
    assert coverage.score == 0.5
    report = agent.contract_report or {}
    assert report["repair_triggered"] is True
    assert report["patch_applied_claims"] == ["cl1", "cl2", "cl3"]


async def test_v124_patch_cannot_change_support_status() -> None:
    bad = {
        "fixes": [
            {
                "claim_id": "cl2",
                "support_status": "insufficient_evidence",
                "evidence_refs": [{"context_id": "C1", "quote": FIXED_QUOTE}],
            }
        ]
    }
    agent, llm = _agent(
        "faithfulness",
        [json.dumps(Q23_RAW, ensure_ascii=False), json.dumps(bad, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    assert result.error_type == "StructuredOutputError"
    report = agent.contract_report or {}
    assert report["final_errors"]
    assert report["final_errors"][0]["code"] == "patch_schema_invalid"


async def test_v124_patch_noncontiguous_quote_is_rejected() -> None:
    bad = {
        "fixes": [
            {
                "claim_id": "cl2",
                "evidence_refs": [{"context_id": "C1", "quote": "生鲜食品质量问题需在签收后 24 小时内拍照反馈"}],
            }
        ]
    }
    agent, llm = _agent(
        "faithfulness",
        [json.dumps(Q23_RAW, ensure_ascii=False), json.dumps(bad, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_failed"


async def test_v124_initial_schema_failure_has_final_errors_and_no_full_repair() -> None:
    agent, llm = _agent("faithfulness", ["not-json"])

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 1
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "initial_schema_invalid"
    assert report["passed_after_repair"] is False


async def test_v124_null_claim_id_uses_effective_id_without_rewriting() -> None:
    raw = {
        "claims": [
            {
                "claim_id": None,
                "claim": "订单签收后 7 天内可申请无理由退款",
                "claim_type": "factual_claim",
                "claim_subtype": "policy",
                "support_status": "supported",
                "is_contradictory": False,
                "contradiction_with": [],
                "evidence_refs": [{"context_id": "C1", "quote": "生鲜食品质量问题需在签收后 24 小时内拍照反馈"}],
                "reason": "test",
            }
        ],
        "reason": "",
    }
    patch = {
        "fixes": [
            {
                "claim_id": "cl1",
                "evidence_refs": [{"context_id": "C1", "quote": FIXED_QUOTE}],
            }
        ]
    }
    agent, _ = _agent(
        "faithfulness",
        [json.dumps(raw, ensure_ascii=False), json.dumps(patch, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is True
    assert (result.data or {})["claims"][0]["claim_id"] is None
    assert (result.data or {})["claims"][0]["support_status"] == "supported"


async def test_v124_conflict_claim_requires_two_refs() -> None:
    contexts = ["A 句。B 句。"]
    raw = {
        "claims": [
            {
                "claim_id": "cl1",
                "claim": "A 与 B 存在冲突",
                "claim_type": "factual_claim",
                "claim_subtype": "conflict",
                "support_status": "supported",
                "is_contradictory": False,
                "contradiction_with": [],
                "evidence_refs": [
                    {"context_id": "C1", "quote": "bad1"},
                    {"context_id": "C1", "quote": "bad2"},
                ],
                "reason": "test",
            }
        ],
        "reason": "",
    }
    one_ref = {
        "fixes": [
            {
                "claim_id": "cl1",
                "evidence_refs": [{"context_id": "C1", "quote": "A 句。"}],
            }
        ]
    }
    two_refs = {
        "fixes": [
            {
                "claim_id": "cl1",
                "evidence_refs": [
                    {"context_id": "C1", "quote": "A 句。"},
                    {"context_id": "C1", "quote": "B 句。"},
                ],
            }
        ]
    }

    agent_one, _ = _agent(
        "faithfulness",
        [json.dumps(raw, ensure_ascii=False), json.dumps(one_ref, ensure_ascii=False)],
    )
    result_one = await agent_one.judge(_payload(contexts=contexts))
    assert result_one.success is False

    agent_two, _ = _agent(
        "faithfulness",
        [json.dumps(raw, ensure_ascii=False), json.dumps(two_refs, ensure_ascii=False)],
    )
    result_two = await agent_two.judge(_payload(contexts=contexts))
    assert result_two.success is True


async def test_v124_c_first_sentence_warning() -> None:
    agent, _ = _agent(
        "answer_correctness",
        [
            json.dumps(
                {
                    "score": 0.3,
                    "missing_points": [],
                    "wrong_facts": ["可以按延保政策处理"],
                    "reason": "test",
                },
                ensure_ascii=False,
            )
        ],
    )

    result = await agent.judge(
        {"query": "q", "answer": "可以按延保政策处理。但第 40 天已超过 30 天。", "gold_answer": "不能按 30 天激活条款处理。"}
    )

    assert result.success is True
    report = agent.contract_report or {}
    assert report["correctness_first_sentence_warning"]["score"] == 0.3


async def test_v124_invalid_patch_carries_agent_contract_on_f_and_strict() -> None:
    bad = {
        "fixes": [
            {
                "claim_id": "cl2",
                "support_status": "insufficient_evidence",
                "evidence_refs": [{"context_id": "C1", "quote": FIXED_QUOTE}],
            }
        ]
    }
    agent, _ = _agent(
        "faithfulness",
        [json.dumps(Q23_RAW, ensure_ascii=False), json.dumps(bad, ensure_ascii=False)],
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
    assert faith.status == "invalid"
    assert strict.status == "invalid"
    assert faith.details["agent_contract"]["final_errors"]
    assert strict.details["agent_contract"]["final_errors"]


async def test_v124_patch_string_evidence_refs_has_schema_final_errors() -> None:
    bad = {
        "fixes": [
            {
                "claim_id": "cl2",
                "evidence_refs": '[{"context_id": "C1", "quote": "x"}]',
            }
        ]
    }
    agent, llm = _agent(
        "faithfulness",
        [json.dumps(Q23_RAW, ensure_ascii=False), json.dumps(bad, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_schema_invalid"
    assert report["final_errors"][0]["validation_errors"]
