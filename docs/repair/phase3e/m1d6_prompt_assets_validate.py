"""M1-D-6 v1.2.4 patch-repair static validation (no Judge)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from m1d6_prompt_leakage_audit import run_audit
except ImportError:  # pragma: no cover
    from docs.repair.phase3e.m1d6_prompt_leakage_audit import run_audit

BASE = Path(__file__).resolve().parents[3]
PROMPT_ROOT = BASE / "backend" / "app" / "prompts" / "rag_judge"
VERSION = "v1.2.4"
BASE_VERSION = "v1.2.3"
VERSION_DIR = PROMPT_ROOT / VERSION
OUT_JSON = Path(__file__).resolve().parent / "m1d6-prompt-v1.2.4-validation.json"
OUT_MD = Path(__file__).resolve().parent / "m1d6-prompt-v1.2.4-validation.md"
OUT_SHA = Path(__file__).resolve().parent / "m1d6-prompt-v1.2.4-validation.sha256"

PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
EXPECTED_SHA = {
    "faithfulness.txt": "52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d",
    "answer_correctness.txt": "ca489fcf39691e9a71aec004a01938fb6c70b7b17da3c55fb0ada066e1d24968",
    "answer_relevancy.txt": "f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc",
}
BASE_SHA = {
    "faithfulness.txt": "52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d",
    "answer_correctness.txt": "a5f9e5b2d3d0e1bb80803f8a09e5ea7c980b5e8d1c7b9155e86266de92d493ef",
    "answer_relevancy.txt": "f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc",
}
PATCH_SCHEMA_SHA = "da70dc607aaf70879cf40e3420bc5440829b05d9be344a07907947df8c891cb8"
PATCH_EXAMPLE_SHA = "629d74ac3bba3a36372c8a54796de6c5c91fc59b20a235061e0c86ae39129a47"
OLD_REPAIR_SHA = "e391d9fac1d0be41b08502226997ca8f22d66a74d42a760f0f8ba64e3a895da3"
V123_REPAIR_SHA = "af9c103b85743c851f59b7c89e7b0e5a2d874667fd6eff2a81f3b438d7d38ed3"


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
    prompt_sha = {filename: sha256_text(text) for filename, text in prompts.items()}
    manifest_sha = sha256_bytes((VERSION_DIR / "MANIFEST.json").read_bytes())
    script_sha = sha256_bytes(Path(__file__).read_bytes())
    patch_schema_sha = sha256_bytes(
        (BASE / "backend/app/schemas/agents/rag_judge_patch.py").read_bytes()
    )
    agent_source = (BASE / "backend/app/agents/rag_judge_agent.py").read_text(encoding="utf-8")
    patch_agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=VERSION)
    patch_example = patch_agent._patch_example() or ""
    patch_example_sha = sha256_text(patch_example)
    old_repair = (
        RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.0")._repair_example() or ""
    )
    v123_repair = (
        RagJudgeAgent("faithfulness", llm=object(), prompt_version="v1.2.3")._repair_example() or ""
    )
    leakage = run_audit()

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
        {"check": "prompt_sha256", "ok": prompt_sha == EXPECTED_SHA},
        {
            "check": "faithfulness_unchanged",
            "ok": prompt_sha["faithfulness.txt"] == BASE_SHA["faithfulness.txt"],
        },
        {
            "check": "correctness_changed",
            "ok": prompt_sha["answer_correctness.txt"] != BASE_SHA["answer_correctness.txt"],
        },
        {
            "check": "relevancy_unchanged",
            "ok": prompt_sha["answer_relevancy.txt"] == BASE_SHA["answer_relevancy.txt"],
        },
        {
            "check": "c_first_sentence_rule",
            "ok": "首句/结论矛盾硬上限" in prompts["answer_correctness.txt"]
            and "固定 `0.0–0.2`" in prompts["answer_correctness.txt"],
        },
        {
            "check": "c_no_q23_text",
            "ok": "Q23" not in prompts["answer_correctness.txt"]
            and "生鲜食品" not in prompts["answer_correctness.txt"],
        },
        {
            "check": "patch_schema_sha",
            "ok": manifest.get("patch_schema_sha256") == patch_schema_sha == PATCH_SCHEMA_SHA,
        },
        {
            "check": "patch_example_sha",
            "ok": manifest.get("patch_example_sha256") == patch_example_sha == PATCH_EXAMPLE_SHA,
        },
        {
            "check": "patch_agent_wired",
            "ok": "_apply_evidence_patch" in agent_source
            and "EvidencePatch" in agent_source
            and "effective" in agent_source,
        },
        {
            "check": "quote_validator",
            "ok": manifest.get("quote_validator_sha256") == quote_validator_sha256(),
        },
        {
            "check": "leakage_zero",
            "ok": leakage.get("status") == "pass" and leakage.get("finding_count") == 0,
        },
        {"check": "old_repair_unchanged", "ok": sha256_text(old_repair) == OLD_REPAIR_SHA},
        {"check": "v123_repair_unchanged", "ok": sha256_text(v123_repair) == V123_REPAIR_SHA},
        {
            "check": "v123_integrity",
            "ok": all(
                sha256_text((PROMPT_ROOT / BASE_VERSION / filename).read_text(encoding="utf-8"))
                == BASE_SHA[filename]
                for filename in PROMPT_FILES
            ),
        },
        {
            "check": "strict_not_judge_metric",
            "ok": "faithfulness_strict" not in manifest.get("judge_metrics", []),
        },
        {
            "check": "strict_derived",
            "ok": manifest.get("derived_metrics") == ["faithfulness_strict"],
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    validation = {
        "name": "m1d6-prompt-v1.2.4-validation",
        "kind": "static_prompt_asset_validation_not_judge_run",
        "generated_on": "2026-11-23",
        "status": "pass" if not failed else "fail",
        "prompt_version": VERSION,
        "prompt_status": manifest.get("status"),
        "active": manifest.get("active"),
        "schema_version": manifest.get("schema_version"),
        "rubric_version": manifest.get("rubric_version"),
        "default_prompt_version": manifest.get("default_prompt_version"),
        "contract_repair_version": manifest.get("contract_repair_version"),
        "quote_validator_sha256": manifest.get("quote_validator_sha256"),
        "patch_schema_sha256": patch_schema_sha,
        "patch_example_sha256": patch_example_sha,
        "leakage_audit": {
            "status": leakage.get("status"),
            "finding_count": leakage.get("finding_count"),
            "non_whitelisted_count": leakage.get("non_whitelisted_count"),
            "min_chars": leakage.get("min_chars"),
            "sha256": sha256_bytes(
                (Path(__file__).resolve().parent / "m1d6-prompt-leakage-audit.json").read_bytes()
            )
            if (Path(__file__).resolve().parent / "m1d6-prompt-leakage-audit.json").is_file()
            else None,
        },
        "prompt_sha256": prompt_sha,
        "base_prompt_sha256": BASE_SHA,
        "manifest_sha256": manifest_sha,
        "script_sha256": script_sha,
        "checks": checks,
        "judge_run": False,
        "runtime_activated": False,
    }
    OUT_JSON.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    output_sha = sha256_bytes(OUT_JSON.read_bytes())
    OUT_SHA.write_text(f"{output_sha}  {OUT_JSON.name}\n", encoding="utf-8", newline="\n")
    lines = [
        "# M1-D-6 v1.2.4 静态校验（非 Judge 运行）",
        "",
        "> 状态：`design_draft` / `active=false`；未冻结、未激活、未跑 Judge。",
        f"> version：`{VERSION}`；rubric_version：`{manifest.get('rubric_version')}`",
        f"> F / C / R：`{prompt_sha['faithfulness.txt']}` / "
        f"`{prompt_sha['answer_correctness.txt']}` / "
        f"`{prompt_sha['answer_relevancy.txt']}`",
        f"> patch schema：`{patch_schema_sha}`",
        f"> patch example：`{patch_example_sha}`",
        f"> MANIFEST SHA256：`{manifest_sha}`",
        f"> leakage audit：findings={leakage.get('finding_count')}",
        f"> 校验输出 SHA256：`{output_sha}`",
        "",
        f"- 检查项：{len(checks)}；通过：{len(checks) - len(failed)}；失败：{len(failed)}",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": validation["status"],
                "checks": len(checks),
                "failed": len(failed),
                "manifest_sha256": manifest_sha,
                "output_sha256": output_sha,
                "patch_schema_sha256": patch_schema_sha,
                "patch_example_sha256": patch_example_sha,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if failed:
        raise SystemExit(f"validation failed: {failed}")


if __name__ == "__main__":
    main()
