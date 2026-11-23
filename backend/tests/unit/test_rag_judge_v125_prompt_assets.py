"""v1.2.5 prompt asset and version isolation tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.agents.rag_judge_agent import (
    CLAIM_DECOMPOSITION_VERSION,
    RagJudgeAgent,
    load_judge_prompt,
)

pytestmark = pytest.mark.unit

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "app" / "prompts" / "rag_judge"
PATCH_SCHEMA = (
    Path(__file__).resolve().parents[2] / "app" / "schemas" / "agents" / "rag_judge_patch.py"
)
PATCH_SCHEMA_V125 = (
    Path(__file__).resolve().parents[2] / "app" / "schemas" / "agents" / "rag_judge_patch_v125.py"
)
F_SHA_V124 = "52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d"
F_SHA_V125 = "9c80d4d5cd60ea7c95ad02c71f97ab566cc2fd82e2a2230124ee4b21247b9d8e"
C_SHA = "ca489fcf39691e9a71aec004a01938fb6c70b7b17da3c55fb0ada066e1d24968"
R_SHA = "f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc"
EXPECTED = {
    "v1.2.4": {
        "faithfulness.txt": F_SHA_V124,
        "answer_correctness.txt": C_SHA,
        "answer_relevancy.txt": R_SHA,
    },
    "v1.2.5": {
        "faithfulness.txt": F_SHA_V125,
        "answer_correctness.txt": C_SHA,
        "answer_relevancy.txt": R_SHA,
    },
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_v125_manifest_is_design_draft_and_inactive() -> None:
    manifest = json.loads(
        (PROMPT_ROOT / CLAIM_DECOMPOSITION_VERSION / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == CLAIM_DECOMPOSITION_VERSION
    assert manifest["status"] == "design_draft"
    assert manifest["active"] is False
    assert manifest["frozen"] is False
    assert manifest["runtime_active"] is False
    assert manifest["schema_version"] == "rag_judge_schema_v3"
    assert manifest["rubric_version"] == "v1.2.0"
    assert manifest["default_prompt_version"] == "v1.0.0"


def test_v125_prompt_shas_and_cr_copy() -> None:
    manifest = json.loads(
        (PROMPT_ROOT / CLAIM_DECOMPOSITION_VERSION / "MANIFEST.json").read_text(encoding="utf-8")
    )
    for filename, expected in EXPECTED["v1.2.5"].items():
        text = (PROMPT_ROOT / CLAIM_DECOMPOSITION_VERSION / filename).read_text(encoding="utf-8")
        assert _sha(text) == expected
        assert manifest["prompts"][filename] == expected
    assert (
        EXPECTED["v1.2.5"]["answer_correctness.txt"] == EXPECTED["v1.2.4"]["answer_correctness.txt"]
    )
    assert EXPECTED["v1.2.5"]["answer_relevancy.txt"] == EXPECTED["v1.2.4"]["answer_relevancy.txt"]


def test_v125_faithfulness_contains_new_rules_without_q23_text() -> None:
    prompt = load_judge_prompt(CLAIM_DECOMPOSITION_VERSION, "faithfulness")
    assert "派生结论原子性" in prompt
    assert "一个派生结论 = 一条 `derived` claim" in prompt
    assert "前提 insufficient + 结论 supported" in prompt
    assert "两条独立 derived claim，不得合并" in prompt
    assert "首句/结论与后文冲突" in prompt
    assert "is_contradictory=true" in prompt
    assert "contradiction_with" in prompt
    for token in ("Q23", "生鲜食品", "拍照反馈", "第 2 天"):
        assert token not in prompt


def test_v125_patch_artifacts_match_manifest() -> None:
    manifest = json.loads(
        (PROMPT_ROOT / CLAIM_DECOMPOSITION_VERSION / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert hashlib.sha256(PATCH_SCHEMA_V125.read_bytes()).hexdigest() == (
        "bfc71529c4ef057dec7256c35ad31341cc31924f5a2784469721323f74547f33"
    )
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=CLAIM_DECOMPOSITION_VERSION)
    assert _sha(agent._patch_example_v125()) == (
        "43f48a420ead52cb21f0472a89040de4ef0480cebbe476a104a0edcbc0d62a6d"
    )
    assert (
        manifest["patch_schema_sha256"]
        == hashlib.sha256(PATCH_SCHEMA_V125.read_bytes()).hexdigest()
    )
    assert manifest["patch_example_sha256"] == _sha(agent._patch_example_v125())


def test_v124_assets_are_unchanged() -> None:
    for filename, expected in EXPECTED["v1.2.4"].items():
        text = (PROMPT_ROOT / "v1.2.4" / filename).read_text(encoding="utf-8")
        assert _sha(text) == expected
    assert hashlib.sha256(PATCH_SCHEMA.read_bytes()).hexdigest() == (
        "da70dc607aaf70879cf40e3420bc5440829b05d9be344a07907947df8c891cb8"
    )
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.4")
    assert _sha(agent._patch_example()) == (
        "629d74ac3bba3a36372c8a54796de6c5c91fc59b20a235061e0c86ae39129a47"
    )
