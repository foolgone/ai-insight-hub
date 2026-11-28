"""M1-D-4 v1.2.2 absence/evidence-directness patch and version-isolated repair."""
from __future__ import annotations

import hashlib
import json

import pytest

from app.agents.rag_judge_agent import (
    PROMPT_DIR,
    RagJudgeAgent,
    load_judge_prompt,
    load_prompt_manifest,
)
from app.core.config import settings
from app.schemas.agents.rag_judge import (
    JUDGE_SCHEMA_V1,
    JUDGE_SCHEMA_V3,
    FaithfulnessOutputV3,
)
from app.services.rag_judge_service import _faithfulness_score_v3

pytestmark = pytest.mark.unit

VERSION = "v1.2.2"
BASE_VERSION = "v1.2.1"
PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
OLD_REPAIR_SHA = "e391d9fac1d0be41b08502226997ca8f22d66a74d42a760f0f8ba64e3a895da3"
C1 = "订单签收后 7 天内可申请无理由退款。\n" "审核通过后，款项将在 1-3 个工作日内原路退回。\n" "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_v122_manifest_is_frozen_with_rubric_v120() -> None:
    manifest = load_prompt_manifest(VERSION)

    assert manifest["version"] == VERSION
    assert manifest["status"] == "frozen"
    assert manifest["active"] is False
    assert manifest["frozen"] is True
    assert manifest["schema_version"] == "rag_judge_schema_v3"
    assert manifest["rubric_version"] == "v1.2.0"
    assert manifest["default_prompt_version"] == "v1.0.0"
    assert manifest["repair_example_version"] == "v1.2.2"
    assert set(manifest["prompts"]) == set(PROMPT_FILES)
    assert "faithfulness_strict" in manifest["derived_metrics"]
    assert "faithfulness_strict" not in manifest["judge_metrics"]


def test_v122_prompt_sha_and_cr_inheritance() -> None:
    manifest = load_prompt_manifest(VERSION)
    base_manifest = load_prompt_manifest(BASE_VERSION)

    for filename in PROMPT_FILES:
        metric = filename.removesuffix(".txt")
        text = load_judge_prompt(VERSION, metric)
        assert _sha256_text(text) == manifest["prompts"][filename]

    assert manifest["prompts"]["faithfulness.txt"] != base_manifest["prompts"]["faithfulness.txt"]
    assert (
        manifest["prompts"]["answer_correctness.txt"]
        == base_manifest["prompts"]["answer_correctness.txt"]
    )
    assert (
        manifest["prompts"]["answer_relevancy.txt"]
        == base_manifest["prompts"]["answer_relevancy.txt"]
    )
    assert load_judge_prompt(VERSION, "answer_correctness") == load_judge_prompt(
        BASE_VERSION, "answer_correctness"
    )
    assert load_judge_prompt(VERSION, "answer_relevancy") == load_judge_prompt(
        BASE_VERSION, "answer_relevancy"
    )


def test_v122_is_explicit_and_default_stays_v100(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    default_agent = RagJudgeAgent("faithfulness", llm=object())
    assert default_agent.prompt_version == "v1.0.0"
    assert default_agent.schema_version == JUDGE_SCHEMA_V1
    assert default_agent.metric_version == "v1"

    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    assert agent.prompt_version == VERSION
    assert agent.schema_version == JUDGE_SCHEMA_V3
    assert agent.metric_version == "v3"
    assert agent.rubric_version == "v1.2.0"
    assert agent.prompt_status == "frozen"
    assert agent.prompt_active is False


def test_v122_faithfulness_prompt_has_absence_and_direct_support_rules() -> None:
    text = load_judge_prompt(VERSION, "faithfulness")

    assert "### 3.5 absence 与混合句" in text
    assert "禁止 `claim_type=factual_claim` + `claim_subtype=absence`" in text
    assert "### 5.2 证据必须直接支持 claim" in text
    assert "只支持运费承担，不支持 7 天限制" in text
    assert "找不到直接支持时判 `insufficient_evidence`" in text
    assert "Q21" not in text
    assert "Q23" not in text


def test_v122_repair_example_is_version_isolated() -> None:
    v120 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")
    v121 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.1")
    v122 = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)

    assert _sha256_text(v120._repair_example() or "") == OLD_REPAIR_SHA
    assert _sha256_text(v121._repair_example() or "") == OLD_REPAIR_SHA

    data = json.loads(v122._repair_example() or "{}")
    output = FaithfulnessOutputV3.model_validate(data)
    absence = output.claims[1]
    assert absence.claim_type == "non_factual"
    assert absence.claim_subtype == "absence"
    assert absence.support_status is None
    assert absence.evidence_refs == []


def test_v122_q23_bad_factual_absence_is_invalid() -> None:
    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "该时限是硬性要求，文档未提及例外情形。",
                    "claim_type": "factual_claim",
                    "claim_subtype": "absence",
                    "support_status": "supported",
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "evidence_refs": [
                        {
                            "context_id": "C1",
                            "quote": "订单签收后 7 天内可申请无理由退款。",
                        }
                    ],
                    "reason": "test",
                }
            ]
        },
        contexts=[C1],
    )

    assert coverage.status == "invalid"
    assert coverage.invalid_reason == "contract_violation"
    assert strict.status == "invalid"


def test_v122_q23_good_absence_is_non_factual() -> None:
    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "订单签收后 7 天内可申请无理由退款。",
                    "claim_type": "factual_claim",
                    "claim_subtype": "policy",
                    "support_status": "supported",
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "evidence_refs": [
                        {
                            "context_id": "C1",
                            "quote": "订单签收后 7 天内可申请无理由退款。",
                        }
                    ],
                    "reason": "C1 原文",
                },
                {
                    "claim_id": "cl2",
                    "claim": "文档未提及超时后的申诉渠道。",
                    "claim_type": "non_factual",
                    "claim_subtype": "absence",
                    "support_status": None,
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "evidence_refs": [],
                    "reason": "absence",
                },
            ]
        },
        contexts=[C1],
    )

    assert coverage.status == "evaluated"
    assert coverage.score == 1.0
    assert coverage.details["non_factual_count"] == 1
    assert strict.status == "evaluated"


def test_v122_q21_insufficient_service_scoring_only() -> None:
    """Only Service scoring; does not prove the model's semantic support."""

    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "质量问题不受 7 天无理由限制。",
                    "claim_type": "factual_claim",
                    "claim_subtype": "condition",
                    "support_status": "insufficient_evidence",
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "evidence_refs": [],
                    "reason": "无直接依据",
                }
            ]
        },
        contexts=[C1],
    )

    assert coverage.status == "evaluated"
    assert coverage.score == 0.0
    assert coverage.details["insufficient_evidence_count"] == 1
    assert coverage.details["supported_count"] == 0
    assert strict.status == "skipped"
    assert strict.skipped_reason == "no_decidable_claims"


def test_v122_assets_exist_but_are_inactive() -> None:
    assert (PROMPT_DIR / VERSION / "faithfulness.txt").is_file()
    manifest = load_prompt_manifest(VERSION)
    assert manifest["status"] == "frozen"
    assert manifest["active"] is False
