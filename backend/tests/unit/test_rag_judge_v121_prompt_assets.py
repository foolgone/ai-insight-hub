"""M1-D-2 v1.2.1 evidence-continuity prompt patch and Q11 contract tests."""
from __future__ import annotations

import hashlib

import pytest

from app.agents.rag_judge_agent import (
    PROMPT_DIR,
    RagJudgeAgent,
    load_judge_prompt,
    load_prompt_manifest,
)
from app.core.config import settings
from app.schemas.agents.rag_judge import JUDGE_SCHEMA_V1, JUDGE_SCHEMA_V3
from app.services.rag_judge_service import _faithfulness_score_v3

pytestmark = pytest.mark.unit

VERSION = "v1.2.1"
BASE_VERSION = "v1.2.0"
PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
BASE_PROMPT_SHA = {
    "faithfulness.txt": "b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
C1 = "订单签收后 7 天内可申请无理由退款。\n" "审核通过后，款项将在 1-3 个工作日内原路退回。\n" "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"
BAD_QUOTE = "订单签收后 7 天内可申请无理由退款。" "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"
GOOD_QUOTE = "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _claim(
    *,
    claim: str,
    subtype: str,
    quote: str,
) -> dict:
    return {
        "claim_id": "cl1",
        "claim": claim,
        "claim_type": "factual_claim",
        "claim_subtype": subtype,
        "support_status": "supported",
        "is_contradictory": False,
        "contradiction_with": [],
        "evidence_refs": [{"context_id": "C1", "quote": quote}],
        "reason": "test",
    }


def test_v121_manifest_is_frozen_with_rubric_v120() -> None:
    manifest = load_prompt_manifest(VERSION)

    assert manifest["version"] == VERSION
    assert manifest["status"] == "frozen"
    assert manifest["active"] is False
    assert manifest["frozen"] is True
    assert manifest["schema_version"] == "rag_judge_schema_v3"
    assert manifest["rubric_version"] == "v1.2.0"
    assert manifest["default_prompt_version"] == "v1.0.0"
    assert set(manifest["prompts"]) == set(PROMPT_FILES)
    assert manifest["metric_version_mapping"]["faithfulness"] == "v3"
    assert "faithfulness_strict" in manifest["derived_metrics"]
    assert "faithfulness_strict" not in manifest["judge_metrics"]


def test_v121_prompt_sha_and_cr_inheritance() -> None:
    manifest = load_prompt_manifest(VERSION)
    v120_manifest = load_prompt_manifest(BASE_VERSION)

    for filename in PROMPT_FILES:
        metric = filename.removesuffix(".txt")
        text = load_judge_prompt(VERSION, metric)
        assert _sha256_text(text) == manifest["prompts"][filename]

    assert manifest["prompts"]["faithfulness.txt"] != BASE_PROMPT_SHA["faithfulness.txt"]
    assert (
        manifest["prompts"]["answer_correctness.txt"] == BASE_PROMPT_SHA["answer_correctness.txt"]
    )
    assert manifest["prompts"]["answer_relevancy.txt"] == BASE_PROMPT_SHA["answer_relevancy.txt"]
    assert load_judge_prompt(VERSION, "answer_correctness") == load_judge_prompt(
        BASE_VERSION, "answer_correctness"
    )
    assert load_judge_prompt(VERSION, "answer_relevancy") == load_judge_prompt(
        BASE_VERSION, "answer_relevancy"
    )
    assert v120_manifest["prompts"]["faithfulness.txt"] == BASE_PROMPT_SHA["faithfulness.txt"]


def test_v121_is_explicit_and_default_stays_v100(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_v121_faithfulness_prompt_has_continuity_rules() -> None:
    text = load_judge_prompt(VERSION, "faithfulness")

    assert "一条 `evidence_ref` 只能引用一个连续子串" in text
    assert "不得把两段不相邻的原文拼成一条 `quote`" in text
    assert "5.1 连续性反例" in text
    assert "A。B。C。" in text
    assert "Q11" not in text
    assert "faithfulness_strict" not in text


def test_v121_bad_noncontiguous_quote_is_invalid() -> None:
    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                _claim(
                    claim="签收第 5 天的定制商品不可以无理由退款。",
                    subtype="condition",
                    quote=BAD_QUOTE,
                )
            ]
        },
        contexts=[C1],
    )

    assert coverage.status == "invalid"
    assert coverage.invalid_reason == "contract_violation"
    assert coverage.score is None
    assert coverage.details["validation_errors"][0]["code"] == "quote_not_found"
    assert strict.status == "invalid"
    assert strict.invalid_reason == "contract_violation"


def test_v121_good_contiguous_quote_is_supported() -> None:
    coverage, strict = _faithfulness_score_v3(
        {
            "claims": [
                _claim(
                    claim="定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。",
                    subtype="condition",
                    quote=GOOD_QUOTE,
                )
            ]
        },
        contexts=[C1],
    )

    assert coverage.status == "evaluated"
    assert coverage.score == 1.0
    assert coverage.details["supported_count"] == 1
    assert coverage.details["validation_errors"] == []
    assert strict.status == "evaluated"
    assert strict.score == 1.0


def test_v121_assets_exist_but_are_inactive() -> None:
    assert (PROMPT_DIR / VERSION / "faithfulness.txt").is_file()
    manifest = load_prompt_manifest(VERSION)
    assert manifest["status"] == "frozen"
    assert manifest["active"] is False
