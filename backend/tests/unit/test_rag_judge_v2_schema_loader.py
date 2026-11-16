"""v1.1.1 Schema / Prompt loader（默认关闭、显式版本、MANIFEST/SHA 校验）。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.agents.rag_judge_agent import (
    PROMPT_DIR,
    RagJudgeAgent,
    RagJudgePromptError,
    load_judge_prompt,
    load_prompt_manifest,
    resolve_prompt_version,
)
from app.core.config import settings
from app.schemas.agents.rag_judge import (
    JUDGE_SCHEMA_V1,
    JUDGE_SCHEMA_V2,
    FaithfulnessOutput,
    judge_schema_version,
    metric_version_for_prompt,
)

pytestmark = pytest.mark.unit


def _agent(metric: str = "faithfulness", *, prompt_version: str | None = None) -> RagJudgeAgent:
    return RagJudgeAgent(
        metric,  # type: ignore[arg-type]
        llm=object(),
        prompt_version=prompt_version,
    )


def test_default_prompt_version_is_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    agent = _agent()

    assert resolve_prompt_version() == "v1.0.0"
    assert agent.prompt_version == "v1.0.0"
    assert agent.schema_version == JUDGE_SCHEMA_V1
    assert agent.metric_version == "v1"
    manifest = load_prompt_manifest("v1.0.0")
    expected = manifest["prompts"]["faithfulness.txt"]
    assert agent.prompt_sha256 == expected


def test_v111_directory_does_not_activate_by_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (PROMPT_DIR / "v1.1.1" / "faithfulness.txt").is_file()
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    agent = _agent()

    assert agent.prompt_version == "v1.0.0"
    assert agent.schema_version == JUDGE_SCHEMA_V1


def test_explicit_v111_loads_v2_prompt_and_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.1.1")

    agent = _agent()

    assert agent.prompt_version == "v1.1.1"
    assert agent.schema_version == JUDGE_SCHEMA_V2
    assert agent.rubric_version == "v1.1.1"
    assert agent.metric_version == "v2"
    manifest = load_prompt_manifest("v1.1.1")
    assert agent.prompt_sha256 == manifest["prompts"]["faithfulness.txt"]


def test_explicit_constructor_version_overrides_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    agent = _agent(prompt_version="v1.1.1")

    assert agent.prompt_version == "v1.1.1"
    assert agent.schema_version == JUDGE_SCHEMA_V2
    assert agent.metric_version == "v2"


def test_prompt_schema_and_metric_mapping() -> None:
    assert judge_schema_version("v1.0.0") == JUDGE_SCHEMA_V1
    assert judge_schema_version("v1.1.0") == JUDGE_SCHEMA_V1
    assert judge_schema_version("v1.1.1") == JUDGE_SCHEMA_V2
    assert metric_version_for_prompt("faithfulness", "v1.1.1") == "v2"
    assert metric_version_for_prompt("faithfulness", "v1.0.0") == "v1"
    assert metric_version_for_prompt("answer_correctness", "v1.1.1") == "v2"


def test_missing_version_directory_raises() -> None:
    with pytest.raises(RagJudgePromptError, match="manifest missing"):
        load_judge_prompt("v9.9.9", "faithfulness")


def test_agent_with_missing_explicit_version_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v9.9.9")

    with pytest.raises(RagJudgePromptError, match="manifest missing"):
        _agent()


def test_missing_manifest_raises(tmp_path: Path) -> None:
    version_dir = tmp_path / "v1.0.0"
    version_dir.mkdir()
    (version_dir / "faithfulness.txt").write_text("prompt", encoding="utf-8")

    with pytest.raises(RagJudgePromptError, match="manifest missing"):
        load_judge_prompt("v1.0.0", "faithfulness", prompt_dir=tmp_path)


def test_manifest_version_mismatch_raises(tmp_path: Path) -> None:
    version_dir = tmp_path / "v1.0.0"
    version_dir.mkdir()
    (version_dir / "faithfulness.txt").write_text("prompt", encoding="utf-8")
    (version_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": "v9.9.9",
                "prompts": {"faithfulness.txt": hashlib.sha256(b"prompt").hexdigest()},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RagJudgePromptError, match="version mismatch"):
        load_judge_prompt("v1.0.0", "faithfulness", prompt_dir=tmp_path)


def test_sha_mismatch_raises(tmp_path: Path) -> None:
    version_dir = tmp_path / "v1.0.0"
    version_dir.mkdir()
    (version_dir / "faithfulness.txt").write_text("prompt", encoding="utf-8")
    (version_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": "v1.0.0",
                "prompts": {"faithfulness.txt": "0" * 64},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RagJudgePromptError, match="sha256 mismatch"):
        load_judge_prompt("v1.0.0", "faithfulness", prompt_dir=tmp_path)


def test_missing_prompt_file_raises(tmp_path: Path) -> None:
    version_dir = tmp_path / "v1.0.0"
    version_dir.mkdir()
    (version_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": "v1.0.0",
                "prompts": {"faithfulness.txt": hashlib.sha256(b"prompt").hexdigest()},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RagJudgePromptError, match="prompt missing"):
        load_judge_prompt("v1.0.0", "faithfulness", prompt_dir=tmp_path)


def test_unregistered_metric_raises(tmp_path: Path) -> None:
    version_dir = tmp_path / "v1.0.0"
    version_dir.mkdir()
    (version_dir / "faithfulness.txt").write_text("prompt", encoding="utf-8")
    (version_dir / "MANIFEST.json").write_text(
        json.dumps(
            {
                "version": "v1.0.0",
                "prompts": {"faithfulness.txt": hashlib.sha256(b"prompt").hexdigest()},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RagJudgePromptError, match="not registered"):
        load_judge_prompt("v1.0.0", "answer_correctness", prompt_dir=tmp_path)


def test_v1_claim_schema_still_parses_supported_and_evidence() -> None:
    output = FaithfulnessOutput.model_validate(
        {
            "claims": [
                {
                    "claim": "退款 1-3 天到账",
                    "supported": True,
                    "evidence": ["1-3 天内到账"],
                    "reason": "上下文明确",
                }
            ],
            "reason": "ok",
        }
    )

    claim = output.claims[0]
    assert claim.supported is True
    assert claim.evidence == ["1-3 天内到账"]
    assert claim.claim_type == "factual_claim"
    assert claim.support_status is None
    assert claim.evidence_refs == []


def test_v2_claim_schema_parses_new_fields() -> None:
    output = FaithfulnessOutput.model_validate(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "订单签收后 7 天内可申请无理由退款",
                    "claim_type": "factual_claim",
                    "claim_subtype": "policy",
                    "support_status": "supported",
                    "evidence_refs": [{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
                    "is_contradictory": False,
                    "contradiction_with": [],
                    "reason": "§1 原文",
                },
                {
                    "claim_id": "cl2",
                    "claim": "文档未提及货到付款",
                    "claim_type": "non_factual",
                    "claim_subtype": "absence",
                    "support_status": None,
                    "evidence_refs": [],
                },
            ],
            "reason": "ok",
        }
    )

    first, second = output.claims
    assert first.claim_id == "cl1"
    assert first.support_status == "supported"
    assert first.evidence_refs[0].context_id == "C1"
    assert second.claim_type == "non_factual"
    assert second.support_status is None


def test_v2_claim_schema_allows_missing_legacy_supported() -> None:
    output = FaithfulnessOutput.model_validate(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "x",
                    "claim_type": "factual_claim",
                    "claim_subtype": "policy",
                    "support_status": "insufficient_evidence",
                }
            ]
        }
    )

    assert output.claims[0].supported is None
    assert output.claims[0].support_status == "insufficient_evidence"
