"""M1-D-5 v1.2.3 prompt asset + contract-repair static validation (no Judge)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
PROMPT_ROOT = BASE / "backend" / "app" / "prompts" / "rag_judge"
VERSION = "v1.2.3"
BASE_VERSION = "v1.2.2"
VERSION_DIR = PROMPT_ROOT / VERSION
OUT_JSON = Path(__file__).resolve().parent / "m1d5-prompt-v1.2.3-validation.json"
OUT_MD = Path(__file__).resolve().parent / "m1d5-prompt-v1.2.3-validation.md"
OUT_SHA = Path(__file__).resolve().parent / "m1d5-prompt-v1.2.3-validation.sha256"

PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
EXPECTED_SHA = {
    "faithfulness.txt": "4f3b9739b2f839f95de159542e2546ff9df96203b1a69fead227e9b8c399f0bf",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
BASE_SHA = {
    "faithfulness.txt": "ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
OLD_REPAIR_SHA = "e391d9fac1d0be41b08502226997ca8f22d66a74d42a760f0f8ba64e3a895da3"
V122_REPAIR_SHA = "7541fe3f4d079f2c173ae6347a247b9614de14f30f761d216c1267bc4a591869"
Q23_FIXTURE_SENTENCE = "生鲜食品签收后不支持无理由退货，质量问题需在签收后 24 小时内拍照反馈。"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import sys

    sys.path.insert(0, str(BASE / "backend"))
    from app.agents.rag_judge_agent import RagJudgeAgent
    from app.schemas.agents.rag_judge_evidence import quote_validator_sha256

    manifest = load_json(VERSION_DIR / "MANIFEST.json")
    prompts = {
        filename: (VERSION_DIR / filename).read_text(encoding="utf-8") for filename in PROMPT_FILES
    }
    base_prompts = {
        filename: (PROMPT_ROOT / BASE_VERSION / filename).read_text(encoding="utf-8")
        for filename in PROMPT_FILES
    }
    prompt_sha = {filename: sha256_text(text) for filename, text in prompts.items()}
    manifest_sha = sha256_bytes((VERSION_DIR / "MANIFEST.json").read_bytes())
    script_sha = sha256_bytes(Path(__file__).read_bytes())
    schema_source = (BASE / "backend/app/schemas/agents/rag_judge.py").read_text(encoding="utf-8")
    agent_source = (BASE / "backend/app/agents/rag_judge_agent.py").read_text(encoding="utf-8")
    service_source = (BASE / "backend/app/services/rag_judge_service.py").read_text(
        encoding="utf-8"
    )
    schema_version = (VERSION_DIR / "version.txt").read_text(encoding="utf-8").strip()
    faithfulness = prompts["faithfulness.txt"]
    repair_agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    repair_text = repair_agent._repair_example() or ""
    repair_data = json.loads(repair_text)
    old_repair = (
        RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")._repair_example() or ""
    )
    v122_repair = (
        RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.2")._repair_example() or ""
    )

    checks: list[dict[str, Any]] = [
        {"check": "manifest_version", "ok": manifest.get("version") == VERSION},
        {"check": "manifest_status_design_draft", "ok": manifest.get("status") == "design_draft"},
        {"check": "manifest_active_false", "ok": manifest.get("active") is False},
        {"check": "manifest_frozen_false", "ok": manifest.get("frozen") is False},
        {
            "check": "manifest_schema_v3",
            "ok": manifest.get("schema_version") == "rag_judge_schema_v3",
        },
        {"check": "manifest_rubric_v120", "ok": manifest.get("rubric_version") == "v1.2.0"},
        {
            "check": "manifest_default_v100",
            "ok": manifest.get("default_prompt_version") == "v1.0.0",
        },
        {
            "check": "contract_repair_fields",
            "ok": manifest.get("contract_repair_version") == VERSION
            and manifest.get("quote_validation") == "agent_precheck_v1"
            and manifest.get("repair_example_version") == VERSION,
        },
        {
            "check": "quote_validator_sha",
            "ok": manifest.get("quote_validator_sha256") == quote_validator_sha256(),
        },
        {"check": "prompt_sha256", "ok": prompt_sha == EXPECTED_SHA},
        {
            "check": "faithfulness_changed_from_v122",
            "ok": prompt_sha["faithfulness.txt"] != BASE_SHA["faithfulness.txt"],
        },
        {
            "check": "correctness_sha_unchanged",
            "ok": prompts["answer_correctness.txt"] == base_prompts["answer_correctness.txt"]
            and prompt_sha["answer_correctness.txt"] == BASE_SHA["answer_correctness.txt"],
        },
        {
            "check": "relevancy_sha_unchanged",
            "ok": prompts["answer_relevancy.txt"] == base_prompts["answer_relevancy.txt"]
            and prompt_sha["answer_relevancy.txt"] == BASE_SHA["answer_relevancy.txt"],
        },
        {
            "check": "evidence_source_rule",
            "ok": "### 5.3 证据来源与连续复制" in faithfulness
            and "只能从 `contexts` 复制" in faithfulness
            and "不得从 answer 的加粗句" in faithfulness,
        },
        {
            "check": "no_fixture_text_in_prompt",
            "ok": "Q23" not in faithfulness
            and "生鲜食品" not in faithfulness
            and Q23_FIXTURE_SENTENCE not in faithfulness,
        },
        {
            "check": "repair_example_factual_and_absence",
            "ok": repair_data["claims"][0]["claim_type"] == "factual_claim"
            and repair_data["claims"][0]["evidence_refs"]
            and repair_data["claims"][1]["claim_type"] == "non_factual"
            and repair_data["claims"][1]["claim_subtype"] == "absence"
            and repair_data["claims"][1]["support_status"] is None
            and repair_data["claims"][1]["evidence_refs"] == [],
        },
        {
            "check": "repair_example_no_fixture_text",
            "ok": "Q23" not in repair_text
            and "生鲜食品" not in repair_text
            and Q23_FIXTURE_SENTENCE not in repair_text,
        },
        {
            "check": "old_repair_sha_unchanged",
            "ok": sha256_text(old_repair) == OLD_REPAIR_SHA
            and sha256_text(v122_repair) == V122_REPAIR_SHA,
        },
        {
            "check": "v123_schema_mapping",
            "ok": "v1.2.3" in schema_source and "JUDGE_V3_PROMPT_VERSIONS" in schema_source,
        },
        {
            "check": "agent_precheck_wired",
            "ok": "QuoteContractError" in agent_source
            and "detect_mixed_absence" in agent_source
            and "check_claims_evidence" in agent_source,
        },
        {
            "check": "service_shared_validator",
            "ok": "check_quote" in service_source
            and "_agent_contract_details" in service_source
            and "agent_contract" in service_source,
        },
        {
            "check": "strict_not_judge_metric",
            "ok": "faithfulness_strict" not in manifest.get("judge_metrics", []),
        },
        {
            "check": "strict_derived",
            "ok": manifest.get("derived_metrics") == ["faithfulness_strict"],
        },
        {"check": "version_txt", "ok": schema_version == VERSION},
        {
            "check": "base_version_integrity",
            "ok": all(
                sha256_text((PROMPT_ROOT / BASE_VERSION / filename).read_text(encoding="utf-8"))
                == BASE_SHA[filename]
                for filename in PROMPT_FILES
            ),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    validation = {
        "name": "m1d5-prompt-v1.2.3-validation",
        "kind": "static_prompt_asset_validation_not_judge_run",
        "generated_on": "2026-11-22",
        "status": "pass" if not failed else "fail",
        "prompt_version": VERSION,
        "prompt_status": manifest.get("status"),
        "active": manifest.get("active"),
        "schema_version": manifest.get("schema_version"),
        "rubric_version": manifest.get("rubric_version"),
        "default_prompt_version": manifest.get("default_prompt_version"),
        "contract_repair_version": manifest.get("contract_repair_version"),
        "quote_validator_sha256": manifest.get("quote_validator_sha256"),
        "prompt_sha256": prompt_sha,
        "base_prompt_sha256": BASE_SHA,
        "manifest_sha256": manifest_sha,
        "script_sha256": script_sha,
        "checks": checks,
        "judge_run": False,
        "runtime_activated": False,
    }
    OUT_JSON.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    output_sha = sha256_bytes(OUT_JSON.read_bytes())
    OUT_SHA.write_text(f"{output_sha}  {OUT_JSON.name}\n", encoding="utf-8", newline="\n")

    lines = [
        "# M1-D-5 v1.2.3 Prompt 与合同修复静态校验（非 Judge 运行）",
        "",
        "> 状态：`design_draft` / `active=false`；未冻结、未激活、未跑 Judge。",
        f"> version：`{VERSION}`；rubric_version：`{manifest.get('rubric_version')}`",
        f"> Schema / Metric：`{manifest.get('schema_version')}` / `v3`",
        f"> MANIFEST SHA256：`{manifest_sha}`",
        f"> quote validator SHA256：`{manifest.get('quote_validator_sha256')}`",
        f"> 校验输出 SHA256：`{output_sha}`",
        "",
        "## Prompt SHA256",
        "",
        "| 文件 | v1.2.3 | v1.2.2 |",
        "|---|---|---|",
    ]
    for filename in PROMPT_FILES:
        lines.append(f"| `{filename}` | `{prompt_sha[filename]}` | `{BASE_SHA[filename]}` |")
    lines.extend(
        [
            "",
            "## 检查",
            "",
            f"- 检查项：{len(checks)}；通过：{len(checks) - len(failed)}；失败：{len(failed)}",
            "- Agent quote 预校验、共享 validator、repair example、旧版本隔离。",
            "- Prompt/repair example 不含 Q23/生鲜食品/fixture 专属文本。",
            "- 默认仍 v1.0.0；未跑 Judge、未激活、未跑 10/40。",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": validation["status"],
                "checks": len(checks),
                "failed": len(failed),
                "manifest_sha256": manifest_sha,
                "output_sha256": output_sha,
                "prompt_sha256": prompt_sha,
                "quote_validator_sha256": manifest.get("quote_validator_sha256"),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if failed:
        raise SystemExit(f"validation failed: {failed}")


if __name__ == "__main__":
    main()
