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
from app.agents.structured_output import parse_with_repair
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


def test_explicit_v112_loads_v2_prompt() -> None:
    agent = _agent(prompt_version="v1.1.2")

    assert agent.prompt_version == "v1.1.2"
    assert agent.schema_version == JUDGE_SCHEMA_V2
    assert agent.rubric_version == "v1.1.2"
    assert agent.metric_version == "v2"
    manifest = load_prompt_manifest("v1.1.2")
    assert agent.prompt_sha256 == manifest["prompts"]["faithfulness.txt"]


def test_prompt_schema_and_metric_mapping() -> None:
    assert judge_schema_version("v1.0.0") == JUDGE_SCHEMA_V1
    assert judge_schema_version("v1.1.0") == JUDGE_SCHEMA_V1
    assert judge_schema_version("v1.1.1") == JUDGE_SCHEMA_V2
    assert judge_schema_version("v1.1.2") == JUDGE_SCHEMA_V2
    assert metric_version_for_prompt("faithfulness", "v1.1.1") == "v2"
    assert metric_version_for_prompt("faithfulness", "v1.1.2") == "v2"
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


class _NoCallLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        self.calls += 1
        raise AssertionError("null fields must not trigger a repair call")


async def test_v2_null_collections_parse_without_repair() -> None:
    llm = _NoCallLLM()
    payload = json.dumps(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "订单签收后 7 天内可申请无理由退款",
                    "claim_type": "factual_claim",
                    "claim_subtype": "policy",
                    "support_status": "supported",
                    "is_contradictory": None,
                    "contradiction_with": None,
                    "evidence_refs": [
                        {
                            "context_id": "C1",
                            "quote": "订单签收后 7 天内可申请无理由退款。",
                        }
                    ],
                    "reason": None,
                }
            ],
            "reason": None,
        },
        ensure_ascii=False,
    )

    output = await parse_with_repair(text=payload, schema=FaithfulnessOutput, llm=llm)

    claim = output.claims[0]
    assert llm.calls == 0
    assert claim.is_contradictory is False
    assert claim.contradiction_with == []
    assert claim.reason == ""
    assert output.reason == ""
    assert claim.evidence_refs[0].context_id == "C1"


async def test_v2_null_evidence_and_contradiction_lists_parse() -> None:
    llm = _NoCallLLM()
    payload = json.dumps(
        {
            "claims": [
                {
                    "claim_id": "cl1",
                    "claim": "文档未提及货到付款",
                    "claim_type": "non_factual",
                    "claim_subtype": "absence",
                    "support_status": None,
                    "evidence_refs": None,
                    "evidence": None,
                    "contradiction_with": None,
                }
            ]
        }
    )

    output = await parse_with_repair(text=payload, schema=FaithfulnessOutput, llm=llm)

    claim = output.claims[0]
    assert llm.calls == 0
    assert claim.evidence_refs == []
    assert claim.evidence == []
    assert claim.contradiction_with == []


def test_v111_faithfulness_payload_has_explicit_context_ids() -> None:
    agent = _agent(prompt_version="v1.1.1")

    messages = agent._create_agent(
        {"query": "q", "answer": "a", "contexts": ["context one", "context two"]}
    )

    payload = json.loads(messages[1]["content"])
    assert payload["context_ids"] == ["C1", "C2"]
    assert payload["contexts"] == ["context one", "context two"]


def test_v100_faithfulness_payload_has_no_context_ids() -> None:
    agent = _agent(prompt_version="v1.0.0")

    messages = agent._create_agent(
        {"query": "q", "answer": "a", "contexts": ["context one", "context two"]}
    )

    payload = json.loads(messages[1]["content"])
    assert "context_ids" not in payload


def test_v111_repair_example_is_complete_json() -> None:
    agent = _agent(prompt_version="v1.1.1")

    example = json.loads(agent._repair_example() or "{}")

    claim = example["claims"][0]
    assert claim["claim_type"] == "factual_claim"
    assert claim["evidence_refs"][0]["context_id"] == "C1"


def test_v111_correctness_prompt_has_extra_info_rule() -> None:
    text = load_judge_prompt("v1.1.1", "answer_correctness")

    assert "额外但正确" in text
    assert "不扣分" in text
    assert "不用于“多说了正确内容”" in text
    assert "Q01" in text


def test_v111_faithfulness_prompt_has_q23_full_json_and_quote_rule() -> None:
    text = load_judge_prompt("v1.1.1", "faithfulness")

    assert "Few-shot A（Q23" in text
    assert "完整 8 条 JSON" in text
    assert '"claim_id": "cl8"' in text
    assert "连续复制" in text
    assert "不能自造" in text
    assert "需保留问题实物及包装证据" in text


def test_v112_faithfulness_prompt_has_single_line_quote_and_q22() -> None:
    text = load_judge_prompt("v1.1.2", "faithfulness")

    assert "跨行引用必须保留换行" in text
    assert "单行连续子串" in text
    assert "Few-shot E（Q22" in text
    assert "该运费规则无例外说明" in text
    assert "absence，不进分母" in text
    assert "Few-shot F（Q36" in text
    assert "§1 与 §12" in text
    assert "虚拟商品（充值、会员、课程）一经售出不支持退款。" in text
    assert "总起/分类引导句" in text
    assert "虚拟商品必须拆 §1/§12" in text
    assert "文档覆盖范围/章节内容的描述" in text
    assert "未涉及/未说明" in text
    assert "回答中的引用/转述原文" in text
    assert "发货时间为 5 个工作日内" in text
    assert "Few-shot G（Q21" in text
    assert "该限制适用于普通商品" in text
