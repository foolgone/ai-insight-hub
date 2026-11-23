"""v1.2.5 claim decomposition, contradiction, and patch robustness tests."""
from __future__ import annotations

import json
import pytest

from app.agents.base import AgentConfig
from app.agents.rag_judge_agent import (
    CLAIM_DECOMPOSITION_VERSION,
    ContradictionContractError,
    RagJudgeAgent,
)
from app.core.llm import LLMResponse, LLMUsage
from app.schemas.agents.rag_judge import FaithfulnessOutputV3
from app.services.rag_judge_service import _faithfulness_score_v3

pytestmark = pytest.mark.unit

CONTEXT = "延保卡需在购买后 30 天内激活。赠品不享受延保。"
QUOTE_ACTIVATION = "延保卡需在购买后 30 天内激活。"
QUOTE_GIFT = "赠品不享受延保。"


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        del messages, kwargs
        item = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return LLMResponse(
            content=item,
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            model="fake-judge-model",
            latency_ms=1.0,
        )


def _agent(metric: str, responses: list[str]) -> tuple[RagJudgeAgent, FakeLLM]:
    llm = FakeLLM(responses)
    agent = RagJudgeAgent(
        metric,  # type: ignore[arg-type]
        config=AgentConfig(
            name=f"rag_judge_{metric}",
            version=CLAIM_DECOMPOSITION_VERSION,
            max_retries=0,
            timeout=5.0,
            max_tokens=512,
        ),
        llm=llm,
        prompt_version=CLAIM_DECOMPOSITION_VERSION,
    )
    return agent, llm


def _claim(
    claim_id: str,
    claim: str,
    *,
    subtype: str,
    status: str | None,
    refs: list[dict[str, str]] | None = None,
    contradictory: bool = False,
    contradiction_with: list[str] | None = None,
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "claim": claim,
        "claim_type": "factual_claim" if status is not None else "non_factual",
        "claim_subtype": subtype,
        "support_status": status,
        "is_contradictory": contradictory,
        "contradiction_with": contradiction_with or [],
        "evidence_refs": refs or [],
        "reason": "",
    }


def _s1_payload(*, paraphrase: bool = False) -> dict[str, object]:
    derived_text = "购买后第 40 天反馈已超过 30 天激活时限" if paraphrase else "购买后第 40 天已超出 30 天激活期限"
    return {
        "claims": [
            _claim(
                "cl1",
                "可以激活",
                subtype="policy",
                status="unsupported",
                contradictory=True,
                contradiction_with=["cl2"],
            ),
            _claim(
                "cl2",
                derived_text,
                subtype="derived",
                status="supported",
                refs=[{"context_id": "C1", "quote": QUOTE_ACTIVATION}],
            ),
            _claim("cl3", "该延保卡仅适用于主机", subtype="condition", status="insufficient_evidence"),
            _claim(
                "cl4",
                "赠品不享受延保",
                subtype="condition",
                status="supported",
                refs=[{"context_id": "C1", "quote": QUOTE_GIFT}],
            ),
            _claim("cl5", "赠品可延长保修", subtype="condition", status="insufficient_evidence"),
            _claim("cl6", "建议联系客服确认激活状态", subtype="advice", status=None),
            _claim("cl7", "文档未说明赠品是否可延长保修", subtype="absence", status=None),
        ],
        "reason": "",
    }


def _payload(contexts: list[str] | None = None) -> dict[str, object]:
    return {
        "query": "购买后第 40 天还能激活延保卡吗？",
        "answer": "可以激活。……购买后第 40 天已超出 30 天激活期限，因此不能激活。",
        "contexts": contexts or [CONTEXT],
    }


async def test_v125_s1_shape_yields_f_040() -> None:
    agent, llm = _agent(
        "faithfulness",
        [json.dumps(_s1_payload(), ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is True
    assert llm.calls == 1
    coverage, strict = _faithfulness_score_v3(result.data or {}, contexts=[CONTEXT])
    assert coverage.status == "evaluated"
    assert coverage.score == 0.4
    assert coverage.details["supported_count"] == 2
    assert coverage.details["scorable_claim_count"] == 5
    assert strict.score == pytest.approx(0.666667)


async def test_v125_s1_paraphrase_still_f_040() -> None:
    agent, _ = _agent(
        "faithfulness",
        [json.dumps(_s1_payload(paraphrase=True), ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is True
    coverage, _ = _faithfulness_score_v3(result.data or {}, contexts=[CONTEXT])
    assert coverage.status == "evaluated"
    assert coverage.score == 0.4


async def test_v125_independent_derived_claims_are_not_merged() -> None:
    data = {
        "claims": [
            _claim(
                "cl1",
                "可以退款",
                subtype="policy",
                status="unsupported",
                contradictory=True,
                contradiction_with=["cl2"],
            ),
            _claim(
                "cl2",
                "订单签收后 7 天内可申请无理由退款",
                subtype="policy",
                status="supported",
                refs=[{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
            ),
            _claim(
                "cl3",
                "第 10 天已超出 7 天退款期",
                subtype="derived",
                status="supported",
                refs=[{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
            ),
            _claim(
                "cl4",
                "第 40 天已超出 30 天激活期限",
                subtype="derived",
                status="supported",
                refs=[{"context_id": "C2", "quote": QUOTE_ACTIVATION}],
            ),
            _claim("cl5", "该政策适用于所有订单", subtype="policy_scope", status="insufficient_evidence"),
            _claim("cl6", "建议联系客服", subtype="advice", status=None),
        ],
        "reason": "",
    }
    agent, _ = _agent("faithfulness", [json.dumps(data, ensure_ascii=False)])
    contexts = [
        "订单签收后 7 天内可申请无理由退款。",
        CONTEXT,
    ]

    result = await agent.judge(_payload(contexts=contexts))

    assert result.success is True
    derived = [
        claim for claim in (result.data or {})["claims"] if claim["claim_subtype"] == "derived"
    ]
    assert len(derived) == 2
    coverage, _ = _faithfulness_score_v3(result.data or {}, contexts=contexts)
    assert coverage.details["scorable_claim_count"] == 5
    assert coverage.score == pytest.approx(0.6)


def _contradiction_output(
    *,
    contradictory: bool,
    refs: list[str],
) -> FaithfulnessOutputV3:
    return FaithfulnessOutputV3.model_validate(
        {
            "claims": [
                _claim(
                    "cl1",
                    "可以激活",
                    subtype="policy",
                    status="unsupported",
                    contradictory=contradictory,
                    contradiction_with=refs,
                ),
                _claim(
                    "cl2",
                    "购买后第 40 天已超出 30 天激活期限",
                    subtype="derived",
                    status="supported",
                    refs=[{"context_id": "C1", "quote": QUOTE_ACTIVATION}],
                ),
            ],
            "reason": "",
        }
    )


@pytest.mark.parametrize(
    "contradictory,refs",
    [
        (True, []),
        (False, ["cl2"]),
        (True, [""]),
        (True, ["cl1"]),
        (True, ["cl9"]),
    ],
)
def test_v125_contradiction_reference_integrity(
    contradictory: bool,
    refs: list[str],
) -> None:
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=CLAIM_DECOMPOSITION_VERSION)
    output = _contradiction_output(contradictory=contradictory, refs=refs)

    with pytest.raises(ContradictionContractError):
        agent._validate_contradiction_references(output)


def test_v125_contradiction_reference_normal_passes() -> None:
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=CLAIM_DECOMPOSITION_VERSION)
    output = _contradiction_output(contradictory=True, refs=["cl2"])
    agent._validate_contradiction_references(output)


def _bad_quote_initial() -> dict[str, object]:
    bad = [{"context_id": "C1", "quote": "不存在的句子"}]
    return {
        "claims": [
            _claim("cl1", "购买后第 40 天已超出 30 天激活期限", subtype="derived", status="supported", refs=bad),
            _claim("cl2", "赠品不享受延保", subtype="condition", status="supported", refs=bad),
            _claim("cl3", "延保卡需在购买后 30 天内激活", subtype="policy", status="supported", refs=bad),
        ],
        "reason": "",
    }


async def test_v125_patch_requires_full_coverage() -> None:
    patch = {
        "fixes": [
            {"claim_id": "cl1", "evidence_refs": [{"context_id": "C1", "quote": QUOTE_ACTIVATION}]},
            {"claim_id": "cl2", "evidence_refs": [{"context_id": "C1", "quote": QUOTE_GIFT}]},
        ]
    }
    agent, llm = _agent(
        "faithfulness",
        [
            json.dumps(_bad_quote_initial(), ensure_ascii=False),
            json.dumps(patch, ensure_ascii=False),
        ],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_incomplete"
    assert report["patch_missing_claims"] == ["cl3"]


async def test_v125_refusal_requires_full_coverage() -> None:
    refusal = {
        "refusal": {
            "claim_ids": ["cl1", "cl2"],
            "reason_code": "no_direct_quote",
            "reason": "cannot find direct quotes",
        }
    }
    agent, llm = _agent(
        "faithfulness",
        [
            json.dumps(_bad_quote_initial(), ensure_ascii=False),
            json.dumps(refusal, ensure_ascii=False),
        ],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_refusal_incomplete"
    assert report["patch_missing_claims"] == ["cl3"]


async def test_v125_full_refusal_is_invalid() -> None:
    refusal = {
        "refusal": {
            "claim_ids": ["cl1", "cl2", "cl3"],
            "reason_code": "no_direct_quote",
            "reason": "cannot find direct quotes",
        }
    }
    agent, llm = _agent(
        "faithfulness",
        [
            json.dumps(_bad_quote_initial(), ensure_ascii=False),
            json.dumps(refusal, ensure_ascii=False),
        ],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_refused"
    assert report["patch_refusal"]["claim_ids"] == ["cl1", "cl2", "cl3"]


async def test_v125_fixes_and_refusal_is_schema_invalid() -> None:
    payload = {
        "fixes": [
            {"claim_id": "cl1", "evidence_refs": [{"context_id": "C1", "quote": QUOTE_ACTIVATION}]}
        ],
        "refusal": {
            "claim_ids": ["cl2", "cl3"],
            "reason_code": "no_direct_quote",
            "reason": "cannot find direct quotes",
        },
    }
    agent, llm = _agent(
        "faithfulness",
        [
            json.dumps(_bad_quote_initial(), ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
        ],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    assert llm.calls == 2
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_schema_invalid"


async def test_v125_unsupported_empty_refs_allowed() -> None:
    initial = {
        "claims": [
            _claim(
                "cl1",
                "可以激活",
                subtype="policy",
                status="unsupported",
                refs=[{"context_id": "C1", "quote": "不存在的句子"}],
            ),
            _claim(
                "cl2",
                "购买后第 40 天已超出 30 天激活期限",
                subtype="derived",
                status="supported",
                refs=[{"context_id": "C1", "quote": "不存在的句子"}],
            ),
        ],
        "reason": "",
    }
    patch = {
        "fixes": [
            {"claim_id": "cl1", "evidence_refs": []},
            {"claim_id": "cl2", "evidence_refs": [{"context_id": "C1", "quote": QUOTE_ACTIVATION}]},
        ]
    }
    agent, _ = _agent(
        "faithfulness",
        [json.dumps(initial, ensure_ascii=False), json.dumps(patch, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is True
    report = agent.contract_report or {}
    assert report["patch_applied_claims"] == ["cl1", "cl2"]
    assert report["patch_unsupported_quote_claims"] == []


async def test_v125_unsupported_nonempty_refs_are_flagged_for_review() -> None:
    initial = {
        "claims": [
            _claim(
                "cl1",
                "可以激活",
                subtype="policy",
                status="unsupported",
                refs=[{"context_id": "C1", "quote": "不存在的句子"}],
            )
        ],
        "reason": "",
    }
    patch = {
        "fixes": [
            {"claim_id": "cl1", "evidence_refs": [{"context_id": "C1", "quote": QUOTE_ACTIVATION}]}
        ]
    }
    agent, _ = _agent(
        "faithfulness",
        [json.dumps(initial, ensure_ascii=False), json.dumps(patch, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is True
    report = agent.contract_report or {}
    assert report["patch_unsupported_quote_claims"] == ["cl1"]
    assert report["patch_semantic_review_required"] is True


async def test_v125_supported_empty_refs_is_invalid() -> None:
    initial = {
        "claims": [
            _claim(
                "cl1",
                "购买后第 40 天已超出 30 天激活期限",
                subtype="derived",
                status="supported",
                refs=[{"context_id": "C1", "quote": "不存在的句子"}],
            )
        ],
        "reason": "",
    }
    patch = {"fixes": [{"claim_id": "cl1", "evidence_refs": []}]}
    agent, _ = _agent(
        "faithfulness",
        [json.dumps(initial, ensure_ascii=False), json.dumps(patch, ensure_ascii=False)],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_empty_refs_for_supported"


async def test_v125_noncontiguous_quote_is_invalid() -> None:
    patch = {
        "fixes": [
            {
                "claim_id": "cl1",
                "evidence_refs": [{"context_id": "C1", "quote": QUOTE_ACTIVATION}],
            },
            {
                "claim_id": "cl2",
                "evidence_refs": [{"context_id": "C1", "quote": QUOTE_GIFT}],
            },
            {
                "claim_id": "cl3",
                "evidence_refs": [{"context_id": "C1", "quote": "延保卡需在购买后 30 天激活"}],
            },
        ]
    }
    agent, _ = _agent(
        "faithfulness",
        [
            json.dumps(_bad_quote_initial(), ensure_ascii=False),
            json.dumps(patch, ensure_ascii=False),
        ],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_quote_invalid"


async def test_v125_patch_null_is_schema_invalid() -> None:
    patch = {
        "fixes": [
            {"claim_id": "cl1", "evidence_refs": None},
            {"claim_id": "cl2", "evidence_refs": None},
            {"claim_id": "cl3", "evidence_refs": None},
        ]
    }
    agent, _ = _agent(
        "faithfulness",
        [
            json.dumps(_bad_quote_initial(), ensure_ascii=False),
            json.dumps(patch, ensure_ascii=False),
        ],
    )

    result = await agent.judge(_payload())

    assert result.success is False
    report = agent.contract_report or {}
    assert report["final_errors"][0]["code"] == "patch_schema_invalid"


def test_v125_and_v124_patch_examples_are_versioned() -> None:
    v125 = RagJudgeAgent("faithfulness", llm=object(), prompt_version=CLAIM_DECOMPOSITION_VERSION)
    v124 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.4")
    assert v125._patch_example_v125() != v124._patch_example()
    assert '"evidence_refs": []' in v125._patch_example_v125()
