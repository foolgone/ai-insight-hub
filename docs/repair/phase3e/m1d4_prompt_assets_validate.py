"""M1-D-4 v1.2.2 prompt asset validation (no Judge run)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
PROMPT_ROOT = BASE / "backend" / "app" / "prompts" / "rag_judge"
VERSION = "v1.2.2"
BASE_VERSION = "v1.2.1"
VERSION_DIR = PROMPT_ROOT / VERSION
OUT_JSON = Path(__file__).resolve().parent / "m1d4-prompt-v1.2.2-validation.json"
OUT_MD = Path(__file__).resolve().parent / "m1d4-prompt-v1.2.2-validation.md"
OUT_SHA = Path(__file__).resolve().parent / "m1d4-prompt-v1.2.2-validation.sha256"

PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
EXPECTED_SHA = {
    "faithfulness.txt": "ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
BASE_SHA = {
    "faithfulness.txt": "9efdc64df1eebafa727bc0946a03192c2d9e9907bd7a3170f867f19774211068",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_integrity(version: str) -> list[dict[str, Any]]:
    manifest = load_json(PROMPT_ROOT / version / "MANIFEST.json")
    checks: list[dict[str, Any]] = []
    for filename, expected in manifest["prompts"].items():
        path = PROMPT_ROOT / version / filename
        checks.append(
            {
                "check": f"{version}_{filename}_sha256",
                "ok": path.is_file() and sha256_text(path.read_text(encoding="utf-8")) == expected,
            }
        )
    return checks


def main() -> None:
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
    faithfulness = prompts["faithfulness.txt"]
    checks: list[dict[str, Any]] = [
        {"check": "manifest_version", "ok": manifest.get("version") == VERSION},
        {"check": "manifest_status_frozen", "ok": manifest.get("status") == "frozen"},
        {"check": "manifest_active_false", "ok": manifest.get("active") is False},
        {"check": "manifest_frozen_true", "ok": manifest.get("frozen") is True},
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
            "check": "repair_example_version",
            "ok": manifest.get("repair_example_version") == VERSION
            and manifest.get("agent_repair_example_required") is True,
        },
        {
            "check": "prompt_files_registered",
            "ok": set(manifest.get("prompts", {})) == set(PROMPT_FILES),
        },
        {"check": "prompt_sha256", "ok": prompt_sha == EXPECTED_SHA},
        {
            "check": "faithfulness_changed_from_v121",
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
            "check": "absence_rule",
            "ok": "### 3.5 absence 与混合句" in faithfulness
            and "禁止 `claim_type=factual_claim` + `claim_subtype=absence`" in faithfulness,
        },
        {
            "check": "direct_support_rule",
            "ok": "### 5.2 证据必须直接支持 claim" in faithfulness and "只支持运费承担，不支持 7 天限制" in faithfulness,
        },
        {
            "check": "no_case_specific_ids",
            "ok": "Q21" not in faithfulness and "Q23" not in faithfulness,
        },
        {
            "check": "strict_not_judge_metric",
            "ok": "faithfulness_strict" not in manifest.get("judge_metrics", []),
        },
        {
            "check": "strict_derived",
            "ok": manifest.get("derived_metrics") == ["faithfulness_strict"],
        },
        {
            "check": "v122_schema_mapping",
            "ok": "v1.2.2" in schema_source and "JUDGE_V3_PROMPT_VERSIONS" in schema_source,
        },
        {
            "check": "repair_branch_isolated",
            "ok": 'self.prompt_version == "v1.2.2"' in agent_source
            and "absence 不需要证据" in agent_source,
        },
        *prompt_integrity(BASE_VERSION),
    ]
    failed = [check for check in checks if not check["ok"]]
    validation = {
        "name": "m1d4-prompt-v1.2.2-validation",
        "kind": "static_prompt_asset_validation_not_judge_run",
        "generated_on": "2026-11-22",
        "status": "pass" if not failed else "fail",
        "prompt_version": VERSION,
        "prompt_status": manifest.get("status"),
        "active": manifest.get("active"),
        "schema_version": manifest.get("schema_version"),
        "rubric_version": manifest.get("rubric_version"),
        "default_prompt_version": manifest.get("default_prompt_version"),
        "repair_example_version": manifest.get("repair_example_version"),
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
        "# M1-D-4 v1.2.2 Prompt 资产校验（非 Judge 运行）",
        "",
        "> 状态：`frozen` / `active=false`；metadata-only 冻结，未激活、未跑 Judge。",
        f"> version：`{VERSION}`；rubric_version：`{manifest.get('rubric_version')}`",
        f"> Schema / Metric：`{manifest.get('schema_version')}` / `v3`",
        f"> MANIFEST SHA256：`{manifest_sha}`",
        f"> 校验输出 SHA256：`{output_sha}`",
        "",
        "## Prompt SHA256",
        "",
        "| 文件 | v1.2.2 | v1.2.1 |",
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
            "- 只改 F absence/直接支持；C/R SHA 与 v1.2.1 一致。",
            "- repair example 版本隔离要求已记录；旧版本示例由 pytest 断言。",
            "- 默认仍 v1.0.0；未跑 Judge、未激活、未跑 40。",
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
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if failed:
        raise SystemExit(f"validation failed: {failed}")


if __name__ == "__main__":
    main()
