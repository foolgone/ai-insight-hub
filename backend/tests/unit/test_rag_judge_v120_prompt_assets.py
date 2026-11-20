"""M1-D-0：v1.2.0 design_draft Prompt 资产、loader 与 Schema v3 校验。"""
from __future__ import annotations

import hashlib
import json
import re

import pytest
from pydantic import ValidationError

from app.agents.rag_judge_agent import (
    RagJudgeAgent,
    load_judge_prompt,
    load_prompt_manifest,
    resolve_prompt_version,
)
from app.core.config import settings
from app.schemas.agents.rag_judge import (
    FACTUAL_CLAIM_SUBTYPES_V3,
    JUDGE_SCHEMA_V1,
    JUDGE_SCHEMA_V3,
    NON_FACTUAL_CLAIM_SUBTYPES_V3,
    FaithfulnessClaimV3,
    FaithfulnessOutputV3,
)

pytestmark = pytest.mark.unit

VERSION = "v1.2.0"
PROMPT_FILES = (
    "faithfulness.txt",
    "answer_correctness.txt",
    "answer_relevancy.txt",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _first_claims_payload(text: str) -> dict:
    for raw in re.findall(r"```json\n(.*?)\n```", text, re.S):
        payload = json.loads(raw)
        if isinstance(payload, dict) and "claims" in payload:
            return payload
    raise AssertionError("prompt must contain a fenced claims JSON example")


def test_manifest_is_design_draft_v3_and_inactive() -> None:
    manifest = load_prompt_manifest(VERSION)

    assert manifest["version"] == VERSION
    assert manifest["status"] == "design_draft"
    assert manifest["active"] is False
    assert manifest["frozen"] is False
    assert manifest["runtime_active"] is False
    assert manifest["schema_version"] == "rag_judge_schema_v3"
    assert manifest["rubric_version"] == VERSION
    assert manifest["default_prompt_version"] == "v1.0.0"
    assert manifest["derived_metrics"] == ["faithfulness_strict"]
    assert "faithfulness_strict" not in manifest["judge_metrics"]
    assert set(manifest["prompts"]) == set(PROMPT_FILES)


def test_prompt_sha256_matches_manifest() -> None:
    manifest = load_prompt_manifest(VERSION)

    for filename in PROMPT_FILES:
        metric = filename.removesuffix(".txt")
        text = load_judge_prompt(VERSION, metric)
        assert text
        assert _sha256_text(text) == manifest["prompts"][filename]


def test_v120_is_explicit_and_default_stays_v100(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    assert resolve_prompt_version() == "v1.0.0"
    default_agent = RagJudgeAgent("faithfulness", llm=object())
    assert default_agent.prompt_version == "v1.0.0"
    assert default_agent.schema_version == JUDGE_SCHEMA_V1
    assert default_agent.metric_version == "v1"

    explicit_agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    assert explicit_agent.prompt_version == VERSION
    assert explicit_agent.schema_version == JUDGE_SCHEMA_V3
    assert explicit_agent.metric_version == "v3"
    assert explicit_agent.rubric_version == VERSION
    assert explicit_agent.prompt_status == "design_draft"
    assert explicit_agent.prompt_active is False
    assert explicit_agent.output_schema is FaithfulnessOutputV3


def test_faithfulness_prompt_covers_all_v3_subtypes() -> None:
    text = load_judge_prompt(VERSION, "faithfulness")

    for subtype in (*FACTUAL_CLAIM_SUBTYPES_V3, *NON_FACTUAL_CLAIM_SUBTYPES_V3):
        assert f"`{subtype}`" in text, f"missing subtype {subtype}"
    assert "`evidence_refs`" in text
    assert "`support_status`" in text
    assert "invalid(contract_violation)" in text
    assert "policy_scope" in text and "policy_relationship" in text
    assert "doc_scope" in text and "doc_relationship" in text
    assert "faithfulness_strict" not in text


def test_v120_prompts_do_not_use_case_specific_ids() -> None:
    for metric in ("faithfulness", "answer_correctness", "answer_relevancy"):
        text = load_judge_prompt(VERSION, metric)
        for index in range(1, 41):
            assert f"Q{index:02d}" not in text


def test_faithfulness_json_skeleton_is_v3_only() -> None:
    text = load_judge_prompt(VERSION, "faithfulness")
    payload = _first_claims_payload(text)

    claim = payload["claims"][0]
    assert set(claim) == {
        "claim_id",
        "claim",
        "claim_type",
        "claim_subtype",
        "support_status",
        "is_contradictory",
        "contradiction_with",
        "evidence_refs",
        "reason",
    }
    assert "supported" not in claim
    assert "evidence" not in claim

    output = FaithfulnessOutputV3.model_validate(payload)
    assert output.claims[0].support_status == "supported"
    assert output.claims[0].evidence_refs[0].context_id == "C1"


def test_v3_claim_rejects_legacy_supported_and_evidence() -> None:
    claim = _first_claims_payload(load_judge_prompt(VERSION, "faithfulness"))["claims"][0]
    claim["supported"] = True
    claim["evidence"] = ["旧字段"]

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FaithfulnessClaimV3.model_validate(claim)


def test_v120_assets_do_not_change_v1_v2_prompts() -> None:
    for version, metric in (
        ("v1.0.0", "faithfulness"),
        ("v1.1.1", "faithfulness"),
        ("v1.1.5", "faithfulness"),
        ("v1.1.5", "answer_correctness"),
        ("v1.1.5", "answer_relevancy"),
    ):
        text = load_judge_prompt(version, metric)
        manifest = load_prompt_manifest(version)
        filename = f"{metric}.txt"
        assert _sha256_text(text) == manifest["prompts"][filename]
