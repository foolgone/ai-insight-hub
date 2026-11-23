"""C1：Schema v3 注册、严格 claim、loader/agent 选择与 v1/v2 兼容。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import app.agents.rag_judge_agent as rag_judge_agent
from app.agents.rag_judge_agent import (
    PROMPT_DIR,
    RagJudgeAgent,
    RagJudgePromptError,
    load_judge_prompt,
    load_prompt_manifest,
)
from app.schemas.agents.rag_judge import (
    FACTUAL_CLAIM_SUBTYPES_V3,
    JUDGE_SCHEMA_V1,
    JUDGE_SCHEMA_V2,
    JUDGE_SCHEMA_V3,
    NON_FACTUAL_CLAIM_SUBTYPES_V3,
    FaithfulnessClaimV3,
    FaithfulnessOutput,
    FaithfulnessOutputV3,
    judge_schema_version,
    metric_version_for_prompt,
)
from app.services.rag_judge_service import _faithfulness_score

pytestmark = pytest.mark.unit

_ORIGINAL_LOAD_PROMPT_MANIFEST = rag_judge_agent.load_prompt_manifest


def _v3_claim(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "claim_id": "cl1",
        "claim": "订单签收后 7 天内可申请无理由退款",
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
        "reason": "test",
    }
    base.update(overrides)
    return base


def _write_prompt_root(
    root: Path,
    version: str,
    schema_version: str | None,
    *,
    include_schema: bool = True,
) -> Path:
    version_dir = root / version
    version_dir.mkdir(parents=True)
    prompt = "prompt"
    (version_dir / "faithfulness.txt").write_text(prompt, encoding="utf-8")
    manifest: dict[str, Any] = {
        "version": version,
        "prompts": {
            "faithfulness.txt": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        },
    }
    if include_schema:
        manifest["schema_version"] = schema_version
    (version_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    return root


def _patch_prompt_dir(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    def _load(version: str, **kwargs: Any) -> dict[str, Any]:
        kwargs["prompt_dir"] = root
        return _ORIGINAL_LOAD_PROMPT_MANIFEST(version, **kwargs)

    monkeypatch.setattr(rag_judge_agent, "load_prompt_manifest", _load)


# --------------------------------------------------------------------------- 版本映射


def test_judge_schema_version_mapping() -> None:
    assert judge_schema_version(None) == JUDGE_SCHEMA_V1
    assert judge_schema_version("v1.0.0") == JUDGE_SCHEMA_V1
    assert judge_schema_version("v1.1.0") == JUDGE_SCHEMA_V1
    for version in ("v1.1.1", "v1.1.2", "v1.1.3", "v1.1.4", "v1.1.5"):
        assert judge_schema_version(version) == JUDGE_SCHEMA_V2
    assert judge_schema_version("v1.2.0") == JUDGE_SCHEMA_V3
    assert judge_schema_version("v1.2.1") == JUDGE_SCHEMA_V3
    assert judge_schema_version("v1.2.2") == JUDGE_SCHEMA_V3
    assert judge_schema_version("v1.2.3") == JUDGE_SCHEMA_V3
    assert judge_schema_version("v1.2.4") == JUDGE_SCHEMA_V3
    assert judge_schema_version("v9.9.9") == JUDGE_SCHEMA_V1


def test_metric_version_mapping() -> None:
    for metric in ("faithfulness", "answer_correctness", "answer_relevancy"):
        assert metric_version_for_prompt(metric, "v1.2.0") == "v3"
        assert metric_version_for_prompt(metric, "v1.2.1") == "v3"
        assert metric_version_for_prompt(metric, "v1.2.2") == "v3"
        assert metric_version_for_prompt(metric, "v1.2.3") == "v3"
        assert metric_version_for_prompt(metric, "v1.2.4") == "v3"
        assert metric_version_for_prompt(metric, "v1.1.5") == "v2"
        assert metric_version_for_prompt(metric, "v1.0.0") == "v1"


# --------------------------------------------------------------------------- V3 claim 结构


@pytest.mark.parametrize("subtype", FACTUAL_CLAIM_SUBTYPES_V3)
def test_v3_factual_subtypes_parse(subtype: str) -> None:
    refs = (
        [
            {"context_id": "C1", "quote": "第一处原文"},
            {"context_id": "C2", "quote": "第二处原文"},
        ]
        if subtype == "conflict"
        else [{"context_id": "C1", "quote": "一处原文"}]
    )
    claim = FaithfulnessClaimV3.model_validate(_v3_claim(claim_subtype=subtype, evidence_refs=refs))
    assert claim.claim_subtype == subtype


@pytest.mark.parametrize("subtype", NON_FACTUAL_CLAIM_SUBTYPES_V3)
def test_v3_non_factual_subtypes_parse(subtype: str) -> None:
    claim = FaithfulnessClaimV3.model_validate(
        _v3_claim(
            claim_type="non_factual",
            claim_subtype=subtype,
            support_status=None,
            evidence_refs=[],
        )
    )
    assert claim.claim_subtype == subtype


def test_v3_factual_requires_support_status() -> None:
    with pytest.raises(ValidationError, match="factual_claim requires support_status"):
        FaithfulnessClaimV3.model_validate(_v3_claim(support_status=None))


def test_v3_non_factual_rejects_support_status() -> None:
    with pytest.raises(ValidationError, match="non_factual must not have support_status"):
        FaithfulnessClaimV3.model_validate(
            _v3_claim(
                claim_type="non_factual",
                claim_subtype="absence",
                support_status="supported",
                evidence_refs=[],
            )
        )


def test_v3_supported_requires_evidence_refs() -> None:
    with pytest.raises(ValidationError, match="supported factual_claim requires evidence_refs"):
        FaithfulnessClaimV3.model_validate(_v3_claim(evidence_refs=[]))

    with pytest.raises(ValidationError, match="conflict claim requires at least two evidence_refs"):
        FaithfulnessClaimV3.model_validate(
            _v3_claim(
                claim_subtype="conflict",
                evidence_refs=[{"context_id": "C1", "quote": "只有一处"}],
            )
        )


def test_v3_insufficient_rejects_evidence_refs() -> None:
    with pytest.raises(ValidationError, match="insufficient_evidence must not have evidence_refs"):
        FaithfulnessClaimV3.model_validate(
            _v3_claim(
                support_status="insufficient_evidence",
                evidence_refs=[{"context_id": "C1", "quote": "不应出现"}],
            )
        )


def test_v3_rejects_legacy_fields() -> None:
    claim = _v3_claim()
    claim["supported"] = True
    claim["evidence"] = ["旧字段"]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FaithfulnessClaimV3.model_validate(claim)


def test_v3_rejects_missing_or_invalid_subtype() -> None:
    missing = _v3_claim()
    missing.pop("claim_subtype")
    with pytest.raises(ValidationError):
        FaithfulnessClaimV3.model_validate(missing)

    with pytest.raises(ValidationError):
        FaithfulnessClaimV3.model_validate(_v3_claim(claim_subtype="bogus"))

    with pytest.raises(ValidationError):
        FaithfulnessClaimV3.model_validate(
            _v3_claim(
                claim_type="non_factual",
                claim_subtype="policy",
                support_status=None,
                evidence_refs=[],
            )
        )


def test_v1_v2_payload_still_parses() -> None:
    v1 = FaithfulnessOutput.model_validate(
        {
            "claims": [
                {
                    "claim": "订单签收后 7 天内可申请无理由退款",
                    "supported": True,
                    "evidence": ["订单签收后 7 天内可申请无理由退款。"],
                }
            ]
        }
    )
    assert v1.claims[0].supported is True

    v2 = FaithfulnessOutput.model_validate({"claims": [_v3_claim()]})
    assert v2.claims[0].claim_subtype == "policy"
    assert v2.claims[0].support_status == "supported"


# --------------------------------------------------------------------------- Service guard


def test_faithfulness_score_v3_guard_raises() -> None:
    with pytest.raises(RagJudgePromptError, match="v3 scoring not implemented until C3"):
        _faithfulness_score({"claims": []}, schema_version=JUDGE_SCHEMA_V3)


# --------------------------------------------------------------------------- MANIFEST / Agent


def test_manifest_schema_version_consistency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_root = _write_prompt_root(tmp_path / "bad_v115", "v1.1.5", JUDGE_SCHEMA_V3)
    _patch_prompt_dir(monkeypatch, bad_root)
    with pytest.raises(RagJudgePromptError, match="schema_version mismatch"):
        RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.1.5")

    good_root = _write_prompt_root(tmp_path / "good_v120", "v1.2.0", JUDGE_SCHEMA_V3)
    _patch_prompt_dir(monkeypatch, good_root)
    good = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")
    assert good.schema_version == JUDGE_SCHEMA_V3

    missing_root = _write_prompt_root(
        tmp_path / "missing_v120", "v1.2.0", None, include_schema=False
    )
    _patch_prompt_dir(monkeypatch, missing_root)
    missing = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")
    assert missing.schema_version == JUDGE_SCHEMA_V3

    unknown_root = _write_prompt_root(tmp_path / "unknown_v120", "v1.2.0", "rag_judge_schema_v9")
    _patch_prompt_dir(monkeypatch, unknown_root)
    with pytest.raises(RagJudgePromptError, match="schema_version mismatch"):
        RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")


def test_agent_v3_selects_v3_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write_prompt_root(tmp_path / "v120", "v1.2.0", JUDGE_SCHEMA_V3)
    _patch_prompt_dir(monkeypatch, root)

    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")

    assert agent.schema_version == JUDGE_SCHEMA_V3
    assert agent.metric_version == "v3"
    assert agent.output_schema is FaithfulnessOutputV3
    example = json.loads(agent._repair_example() or "{}")
    claim = example["claims"][0]
    assert claim["claim_subtype"] == "policy"
    assert "evidence_refs" in claim
    assert "supported" not in claim
    assert "evidence" not in claim


def test_agent_v2_repair_example_unchanged() -> None:
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.1.5")

    assert agent.output_schema is FaithfulnessOutput
    example = json.loads(agent._repair_example() or "{}")
    claim = example["claims"][0]
    assert claim["support_status"] == "supported"
    assert "evidence_refs" in claim
    assert "supported" not in claim


def test_v120_prompt_assets_exist_but_are_inactive() -> None:
    assert (PROMPT_DIR / "v1.2.0" / "faithfulness.txt").is_file()
    manifest = load_prompt_manifest("v1.2.0")
    assert manifest["status"] == "frozen"
    assert manifest["active"] is False
    assert manifest["schema_version"] == JUDGE_SCHEMA_V3
    assert load_judge_prompt("v1.2.0", "faithfulness")
