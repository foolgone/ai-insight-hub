"""M1-D-5 v1.2.3 prompt assets, version isolation, and anti-teaching checks."""
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
    judge_schema_version,
)
from app.schemas.agents.rag_judge_evidence import quote_validator_sha256

pytestmark = pytest.mark.unit

VERSION = "v1.2.3"
BASE_VERSION = "v1.2.2"
PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
F_SHA = "4f3b9739b2f839f95de159542e2546ff9df96203b1a69fead227e9b8c399f0bf"
OLD_REPAIR_SHA = "e391d9fac1d0be41b08502226997ca8f22d66a74d42a760f0f8ba64e3a895da3"
V122_REPAIR_SHA = "7541fe3f4d079f2c173ae6347a247b9614de14f30f761d216c1267bc4a591869"
Q23_FIXTURE_SENTENCE = "生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_v123_manifest_is_design_draft() -> None:
    manifest = load_prompt_manifest(VERSION)

    assert manifest["version"] == VERSION
    assert manifest["status"] == "design_draft"
    assert manifest["active"] is False
    assert manifest["frozen"] is False
    assert manifest["runtime_active"] is False
    assert manifest["schema_version"] == "rag_judge_schema_v3"
    assert manifest["rubric_version"] == "v1.2.0"
    assert manifest["default_prompt_version"] == "v1.0.0"
    assert manifest["contract_repair_version"] == "v1.2.3"
    assert manifest["quote_validation"] == "agent_precheck_v1"
    assert manifest["quote_validator_sha256"] == quote_validator_sha256()
    assert manifest["repair_example_version"] == "v1.2.3"


def test_v123_prompt_sha_and_cr_inheritance() -> None:
    manifest = load_prompt_manifest(VERSION)
    base_manifest = load_prompt_manifest(BASE_VERSION)

    for filename in PROMPT_FILES:
        metric = filename.removesuffix(".txt")
        text = load_judge_prompt(VERSION, metric)
        assert _sha256_text(text) == manifest["prompts"][filename]

    assert manifest["prompts"]["faithfulness.txt"] == F_SHA
    assert manifest["prompts"]["faithfulness.txt"] != base_manifest["prompts"]["faithfulness.txt"]
    assert (
        manifest["prompts"]["answer_correctness.txt"]
        == base_manifest["prompts"]["answer_correctness.txt"]
    )
    assert (
        manifest["prompts"]["answer_relevancy.txt"]
        == base_manifest["prompts"]["answer_relevancy.txt"]
    )


def test_v123_default_stays_v100(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RAG_JUDGE_PROMPT_VERSION", "v1.0.0")

    default_agent = RagJudgeAgent("faithfulness", llm=object())
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)

    assert default_agent.prompt_version == "v1.0.0"
    assert default_agent.schema_version == JUDGE_SCHEMA_V1
    assert agent.prompt_version == VERSION
    assert agent.schema_version == JUDGE_SCHEMA_V3
    assert agent.rubric_version == "v1.2.0"
    assert agent.prompt_status == "design_draft"
    assert agent.prompt_active is False


def test_v123_prompt_has_evidence_source_rules() -> None:
    text = load_judge_prompt(VERSION, "faithfulness")

    assert "### 5.3 证据来源与连续复制" in text
    assert "只能从 `contexts` 复制" in text
    assert "不得从 answer 的加粗句" in text
    assert "找不到连续原文时判 `insufficient_evidence`" in text
    assert "不得跳过中间字符" in text


def test_v123_prompt_and_repair_example_are_not_taught_on_q23() -> None:
    text = load_judge_prompt(VERSION, "faithfulness")
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    repair = agent._repair_example() or ""

    for body in (text, repair):
        assert "Q23" not in body
        assert "生鲜食品" not in body
        assert Q23_FIXTURE_SENTENCE not in body


def test_v123_repair_example_has_factual_and_absence() -> None:
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    data = json.loads(agent._repair_example() or "{}")

    assert data["claims"][0]["claim_type"] == "factual_claim"
    assert data["claims"][0]["evidence_refs"]
    assert data["claims"][1]["claim_type"] == "non_factual"
    assert data["claims"][1]["claim_subtype"] == "absence"
    assert data["claims"][1]["support_status"] is None
    assert data["claims"][1]["evidence_refs"] == []
    assert "answer 的截断句不是证据" in data["claims"][0]["reason"]


def test_old_repair_examples_are_unchanged() -> None:
    v120 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")
    v121 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.1")
    v122 = RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.2")

    assert _sha256_text(v120._repair_example() or "") == OLD_REPAIR_SHA
    assert _sha256_text(v121._repair_example() or "") == OLD_REPAIR_SHA
    assert _sha256_text(v122._repair_example() or "") == V122_REPAIR_SHA


def test_v123_schema_mapping() -> None:
    assert judge_schema_version(VERSION) == JUDGE_SCHEMA_V3
    assert (PROMPT_DIR / VERSION / "version.txt").read_text(encoding="utf-8").strip() == VERSION
