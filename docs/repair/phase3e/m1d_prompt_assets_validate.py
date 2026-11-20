"""M1-D-0 prompt asset validation (NOT a Judge run).

Validates the v1.2.0 design_draft assets: manifest fields, prompt SHA256,
Schema v3 subtype coverage, no case-specific IDs, and v1/v2 prompt integrity.

Run:
    python docs/repair/phase3e/m1d_prompt_assets_validate.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
PROMPT_ROOT = BASE / "backend" / "app" / "prompts" / "rag_judge"
VERSION = "v1.2.0"
VERSION_DIR = PROMPT_ROOT / VERSION
OUTPUT_FILE = Path(__file__).resolve().parent / "m1d-prompt-v1.2.0-validation.json"
MD_FILE = Path(__file__).resolve().parent / "m1d-prompt-v1.2.0-validation.md"
SHA_FILE = Path(__file__).resolve().parent / "m1d-prompt-v1.2.0-validation.sha256"

PROMPT_FILES = ("faithfulness.txt", "answer_correctness.txt", "answer_relevancy.txt")
FACTUAL_SUBTYPES = (
    "policy",
    "condition",
    "normative_requirement",
    "fact",
    "process",
    "derived",
    "policy_scope",
    "policy_relationship",
    "conflict",
)
NON_FACTUAL_SUBTYPES = (
    "absence",
    "doc_scope",
    "doc_relationship",
    "uncertainty",
    "meta",
    "advice",
    "greeting",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def first_claims_payload(text: str) -> dict[str, Any]:
    for raw in re.findall(r"```json\n(.*?)\n```", text, re.S):
        payload = json.loads(raw)
        if isinstance(payload, dict) and "claims" in payload:
            return payload
    raise ValueError("no fenced claims JSON example")


def version_prompt_integrity(version: str) -> list[dict[str, Any]]:
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
    manifest_bytes = (VERSION_DIR / "MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    prompts = {
        filename: (VERSION_DIR / filename).read_text(encoding="utf-8") for filename in PROMPT_FILES
    }
    prompt_sha = {filename: sha256_text(text) for filename, text in prompts.items()}
    manifest_sha = sha256_bytes(manifest_bytes)
    script_sha = sha256_bytes(Path(__file__).read_bytes())

    faithfulness = prompts["faithfulness.txt"]
    claims_payload = first_claims_payload(faithfulness)
    claim_keys = set(claims_payload["claims"][0])
    expected_claim_keys = {
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
    case_ids = [f"Q{index:02d}" for index in range(1, 41)]

    checks: list[dict[str, Any]] = [
        {"check": "manifest_version", "ok": manifest.get("version") == VERSION},
        {
            "check": "manifest_status_design_draft",
            "ok": manifest.get("status") == "design_draft",
        },
        {"check": "manifest_active_false", "ok": manifest.get("active") is False},
        {"check": "manifest_frozen_false", "ok": manifest.get("frozen") is False},
        {
            "check": "manifest_schema_v3",
            "ok": manifest.get("schema_version") == "rag_judge_schema_v3",
        },
        {
            "check": "manifest_rubric_v120",
            "ok": manifest.get("rubric_version") == VERSION,
        },
        {
            "check": "manifest_default_v100",
            "ok": manifest.get("default_prompt_version") == "v1.0.0",
        },
        {
            "check": "strict_not_judge_metric",
            "ok": "faithfulness_strict" not in manifest.get("judge_metrics", []),
        },
        {
            "check": "strict_is_derived",
            "ok": manifest.get("derived_metrics") == ["faithfulness_strict"],
        },
        {
            "check": "prompt_files_registered",
            "ok": set(manifest.get("prompts", {})) == set(PROMPT_FILES),
        },
        {
            "check": "prompt_sha256",
            "ok": all(
                manifest["prompts"].get(name) == digest for name, digest in prompt_sha.items()
            ),
        },
        {
            "check": "faithfulness_all_16_subtypes",
            "ok": all(
                f"`{subtype}`" in faithfulness
                for subtype in (*FACTUAL_SUBTYPES, *NON_FACTUAL_SUBTYPES)
            ),
        },
        {
            "check": "faithfulness_v3_fields",
            "ok": claim_keys == expected_claim_keys,
        },
        {
            "check": "faithfulness_invalid_contract",
            "ok": "invalid(contract_violation)" in faithfulness,
        },
        {
            "check": "no_case_ids",
            "ok": all(case_id not in text for text in prompts.values() for case_id in case_ids),
        },
        {
            "check": "strict_not_in_prompt",
            "ok": "faithfulness_strict" not in faithfulness,
        },
        *version_prompt_integrity("v1.0.0"),
        *version_prompt_integrity("v1.1.5"),
    ]

    failed = [check for check in checks if not check["ok"]]
    validation = {
        "name": "m1d-prompt-v1.2.0-validation",
        "kind": "static_prompt_asset_validation_not_judge_run",
        "generated_on": "2026-11-20",
        "status": "pass" if not failed else "fail",
        "prompt_version": VERSION,
        "prompt_status": manifest.get("status"),
        "active": manifest.get("active"),
        "schema_version": manifest.get("schema_version"),
        "rubric_version": manifest.get("rubric_version"),
        "default_prompt_version": manifest.get("default_prompt_version"),
        "prompt_sha256": prompt_sha,
        "manifest_sha256": manifest_sha,
        "script_sha256": script_sha,
        "checks": checks,
        "judge_run": False,
        "runtime_activated": False,
    }
    OUTPUT_FILE.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    output_sha = sha256_bytes(OUTPUT_FILE.read_bytes())
    SHA_FILE.write_text(f"{output_sha}  {OUTPUT_FILE.name}\n", encoding="utf-8", newline="\n")

    lines = [
        "# M1-D-0 v1.2.0 Prompt 资产校验（非 Judge 运行）",
        "",
        "> 状态：`design_draft` / `active=false`；未跑 Judge、未激活、未上生产。",
        f"> Prompt 版本：`{VERSION}`",
        f"> Schema：`{manifest.get('schema_version')}`；rubric：`{manifest.get('rubric_version')}`",
        f"> MANIFEST SHA256：`{manifest_sha}`",
        f"> 校验输出 SHA256：`{output_sha}`",
        "",
        "## Prompt SHA256",
        "",
        "| 文件 | SHA256 |",
        "|---|---|",
    ]
    for filename in PROMPT_FILES:
        lines.append(f"| `{filename}` | `{prompt_sha[filename]}` |")
    lines.extend(
        [
            "",
            "## 检查",
            "",
            f"- 检查项：{len(checks)}；通过：{len(checks) - len(failed)}；失败：{len(failed)}",
            "- 默认版本：`v1.0.0`；v1.2.0 只能显式加载。",
            "- `faithfulness_strict` 只在 `derived_metrics`，不在 `judge_metrics`。",
            "- 未运行 Judge；未修改 v1.0.0/v1.1.x Prompt。",
        ]
    )
    MD_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

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
