"""M1-D-6 v1.2.4 patch assets and C first-sentence rule tests."""
from __future__ import annotations

import hashlib
import json

import pytest

from app.agents.rag_judge_agent import RagJudgeAgent, load_judge_prompt, load_prompt_manifest

pytestmark = pytest.mark.unit

VERSION = "v1.2.4"
BASE_VERSION = "v1.2.3"
F_SHA = "52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d"
C_SHA = "ca489fcf39691e9a71aec004a01938fb6c70b7b17da3c55fb0ada066e1d24968"
R_SHA = "f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc"
PATCH_SCHEMA_SHA = "da70dc607aaf70879cf40e3420bc5440829b05d9be344a07907947df8c891cb8"
PATCH_EXAMPLE_SHA = "629d74ac3bba3a36372c8a54796de6c5c91fc59b20a235061e0c86ae39129a47"


def test_v124_manifest_frozen_and_assets() -> None:
    manifest = load_prompt_manifest(VERSION)

    assert manifest["version"] == VERSION
    assert manifest["status"] == "frozen"
    assert manifest["active"] is False
    assert manifest["frozen"] is True
    assert manifest["rubric_version"] == "v1.2.0"
    assert manifest["default_prompt_version"] == "v1.0.0"
    assert manifest["contract_repair_version"] == "v1.2.4"
    assert manifest["patch_schema_sha256"] == PATCH_SCHEMA_SHA
    assert manifest["patch_example_sha256"] == PATCH_EXAMPLE_SHA
    assert manifest["prompts"]["faithfulness.txt"] == F_SHA
    assert manifest["prompts"]["answer_correctness.txt"] == C_SHA
    assert manifest["prompts"]["answer_relevancy.txt"] == R_SHA


def test_v124_f_unchanged_c_changed_r_unchanged() -> None:
    base = load_prompt_manifest(BASE_VERSION)
    manifest = load_prompt_manifest(VERSION)

    assert manifest["prompts"]["faithfulness.txt"] == base["prompts"]["faithfulness.txt"]
    assert (
        manifest["prompts"]["answer_correctness.txt"] != base["prompts"]["answer_correctness.txt"]
    )
    assert manifest["prompts"]["answer_relevancy.txt"] == base["prompts"]["answer_relevancy.txt"]


def test_v124_c_first_sentence_rule_has_no_q23_text() -> None:
    text = load_judge_prompt(VERSION, "answer_correctness")

    assert "首句/结论矛盾硬上限" in text
    assert "固定 `0.0–0.2`" in text
    assert "Q23" not in text
    assert "生鲜食品" not in text


def test_v124_patch_example_is_evidence_only_and_no_q23_text() -> None:
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    data = json.loads(agent._patch_example())

    assert set(data) == {"fixes"}
    assert set(data["fixes"][0]) == {"claim_id", "evidence_refs"}
    assert "support_status" not in json.dumps(data)
    assert "Q23" not in json.dumps(data, ensure_ascii=False)
    assert "生鲜食品" not in json.dumps(data, ensure_ascii=False)
    assert hashlib.sha256(agent._patch_example().encode()).hexdigest() == PATCH_EXAMPLE_SHA


def test_v124_old_repair_examples_unchanged() -> None:
    v120 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")
    v123 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.3")

    assert (
        hashlib.sha256((v120._repair_example() or "").encode()).hexdigest()
        == "e391d9fac1d0be41b08502226997ca8f22d66a74d42a760f0f8ba64e3a895da3"
    )
    assert (
        hashlib.sha256((v123._repair_example() or "").encode()).hexdigest()
        == "af9c103b85743c851f59b7c89e7b0e5a2d874667fd6eff2a81f3b438d7d38ed3"
    )
