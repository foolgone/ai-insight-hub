"""M1-C C4 40-case inventory (NOT a Judge run).

Reads frozen final labels + target v1.0.2 and writes a reproducible inventory
with counts, special lists, baseline-delta policy, SHA and validation.

Run:
    python docs/repair/phase3e/m1c_c4_inventory.py
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
TARGET_FILE = BASE / "pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "pilot-40-final-labels.json"
OUTPUT_FILE = BASE / "m1c-c4-inventory.json"
MD_FILE = BASE / "m1c-c4-inventory.md"
SHA_FILE = BASE / "m1c-c4-inventory.sha256"
VALIDATION_FILE = BASE / "m1c-c4-inventory.validation.json"

TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"

EXPECTED_GROUP = {"human_gold": 13, "provisional": 27}
EXPECTED_CATEGORY = {
    "direct": 12,
    "constraint": 9,
    "multi": 8,
    "unanswerable": 6,
    "ambiguous": 5,
}
EXPECTED_BASELINE = {"reused": 30, "missing": 6, "new": 2, "available_old_run": 2}
EXPECTED_CONTEXT = {"2": 32, "1": 6, "unavailable": 2}
MISSING_BASELINE = ["Q33", "Q34", "Q37", "Q38", "Q39", "Q40"]
CONTEXT_UNAVAILABLE = ["Q14", "Q33"]
C1_ONLY = ["Q22", "Q26", "Q27", "Q34", "Q37", "Q40"]
AVAILABLE_OLD_RUN = ["Q35", "Q36"]
NEW_BASELINE = ["Q14", "Q32"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def baseline_delta(status: str) -> str:
    if status == "reused":
        return "available"
    if status == "available_old_run":
        return "old_run_only"
    return "unavailable"


def main() -> None:
    target_bytes = TARGET_FILE.read_bytes()
    labels_bytes = LABELS_FILE.read_bytes()
    target_sha = sha256_bytes(target_bytes)
    labels_sha = sha256_bytes(labels_bytes)
    script_sha = sha256_file(Path(__file__))
    target_data = json.loads(target_bytes)
    labels_data = json.loads(labels_bytes)
    targets = {case["case_id"]: case for case in target_data["cases"]}
    labels = labels_data["labels"]

    rows: list[dict[str, Any]] = []
    for label in labels:
        case_id = label["case_id"]
        target = targets[case_id]
        rows.append(
            {
                "case_id": case_id,
                "group": label["group"],
                "final_category": label["final_category"],
                "context_availability": label["context_availability"],
                "baseline_status": label["baseline_status"],
                "baseline_delta": baseline_delta(label["baseline_status"]),
                "target_source": label.get("target_source"),
                "known_issue": label.get("known_issue") or "",
                "targets": target.get("targets") or {},
                "target_status": target.get("target_status"),
            }
        )

    groups = Counter(row["group"] for row in rows)
    categories = Counter(row["final_category"] for row in rows)
    baseline = Counter(row["baseline_status"] for row in rows)
    context = Counter(row["context_availability"] for row in rows)
    target_source = Counter(row["target_source"] for row in rows)
    target_status = Counter(row["target_status"] for row in rows)

    missing = sorted(
        row["case_id"] for row in rows if row["baseline_status"] == "missing"
    )
    unavailable = sorted(
        row["case_id"] for row in rows if row["context_availability"] == "unavailable"
    )
    c1_only = sorted(
        row["case_id"] for row in rows if row["context_availability"] == "1"
    )
    old_run = sorted(
        row["case_id"] for row in rows if row["baseline_status"] == "available_old_run"
    )
    new_baseline = sorted(
        row["case_id"] for row in rows if row["baseline_status"] == "new"
    )
    known_non_pass = sorted(
        row["case_id"] for row in rows if "known_non_pass" in row["known_issue"]
    )
    category_changed = sorted(
        row["case_id"] for row in rows if "category_changed" in row["known_issue"]
    )

    output = {
        "meta": {
            "name": "m1c-c4-inventory",
            "kind": "static_inventory_not_judge_run",
            "generated_on": "2026-11-20",
            "target_file": TARGET_FILE.name,
            "target_sha256": target_sha,
            "labels_file": LABELS_FILE.name,
            "labels_sha256": labels_sha,
            "script_file": Path(__file__).name,
            "script_sha256": script_sha,
            "row_count": len(rows),
            "group_counts": dict(groups),
            "category_counts": dict(categories),
            "baseline_counts": dict(baseline),
            "context_counts": dict(context),
            "target_source_counts": dict(target_source),
            "target_status_counts": dict(target_status),
            "special_lists": {
                "missing_baseline": missing,
                "context_unavailable": unavailable,
                "c1_only": c1_only,
                "available_old_run": old_run,
                "new_baseline": new_baseline,
                "known_non_pass": known_non_pass,
                "category_changed": category_changed,
            },
            "baseline_policy": {
                "missing_baseline": (
                    "baseline_delta: unavailable; exclude from delta/improvement claims"
                ),
                "available_old_run": "old run only; not v1.2.0 measured",
                "context_unavailable": "F unavailable; exclude from F target pass rate",
                "c1_only": "single context; report separately",
            },
            "not_for_runtime": True,
        },
        "cases": rows,
    }
    output_bytes = (json.dumps(output, ensure_ascii=False, indent=1) + "\n").encode(
        "utf-8"
    )
    OUTPUT_FILE.write_bytes(output_bytes)
    output_sha = sha256_bytes(output_bytes)
    SHA_FILE.write_text(
        f"{output_sha}  {OUTPUT_FILE.name}\n", encoding="utf-8", newline="\n"
    )

    lines = [
        "# M1-C C4 40 条完整性盘点（非 Judge 运行）",
        "",
        "> 状态：`static_inventory_not_judge_run`；生成日期 2026-11-20。",
        f"> 目标：`{TARGET_FILE.name}` SHA256 `{target_sha}`",
        f"> 分类：`{LABELS_FILE.name}` SHA256 `{labels_sha}`",
        f"> 脚本：`{Path(__file__).name}` SHA256 `{script_sha}`",
        f"> 输出：`{OUTPUT_FILE.name}` SHA256 `{output_sha}`",
        "",
        "## 计数",
        "",
        f"- total: {len(rows)}",
        f"- group: {dict(groups)}",
        f"- category: {dict(categories)}",
        f"- baseline: {dict(baseline)}",
        f"- context: {dict(context)}",
        "",
        "## 特殊列表",
        "",
        f"- `baseline_missing`: {missing}",
        f"- `baseline_delta`: unavailable for {missing}",
        f"- `context_unavailable`: {unavailable}",
        f"- `c1_only`: {c1_only}",
        f"- `available_old_run`: {old_run}",
        f"- `new_baseline`: {new_baseline}",
        f"- `known_non_pass`: {known_non_pass}",
        f"- `category_changed`: {category_changed}",
        "",
        "## 40 条明细",
        "",
        "| Case | group | category | context | baseline | delta | target F | known issue |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['group']} | {row['final_category']} | "
            f"{row['context_availability']} | {row['baseline_status']} | "
            f"{row['baseline_delta']} | {row['targets'].get('F')} | {row['known_issue']} |"
        )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本文件是静态盘点，不是 Judge 运行；",
            "- `baseline_missing` 不计算 delta，不声称改善/回退；",
            "- Q14/Q33 context_unavailable 不进入 F 目标通过率；",
            "- C1-only 单列；Q35/Q36 只用 old run 参考；",
            "- 未修改 Prompt/Service/Schema/API/DB；未运行 Judge。",
        ]
    )
    MD_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    validation = {
        "name": "m1c-c4-inventory-validation",
        "status": "pass",
        "checks": [
            {"check": "target_sha256", "ok": target_sha == TARGET_SHA},
            {"check": "labels_sha256", "ok": labels_sha == LABELS_SHA},
            {"check": "row_count", "ok": len(rows) == 40},
            {"check": "group_counts", "ok": dict(groups) == EXPECTED_GROUP},
            {"check": "category_counts", "ok": dict(categories) == EXPECTED_CATEGORY},
            {"check": "baseline_counts", "ok": dict(baseline) == EXPECTED_BASELINE},
            {"check": "context_counts", "ok": dict(context) == EXPECTED_CONTEXT},
            {"check": "missing_baseline", "ok": missing == MISSING_BASELINE},
            {"check": "context_unavailable", "ok": unavailable == CONTEXT_UNAVAILABLE},
            {"check": "c1_only", "ok": c1_only == C1_ONLY},
            {"check": "available_old_run", "ok": old_run == AVAILABLE_OLD_RUN},
            {"check": "new_baseline", "ok": new_baseline == NEW_BASELINE},
            {
                "check": "missing_delta_unavailable",
                "ok": all(
                    row["baseline_delta"] == "unavailable"
                    for row in rows
                    if row["baseline_status"] in ("missing", "new")
                ),
            },
        ],
        "output_sha256": output_sha,
    }
    failed = [check for check in validation["checks"] if not check["ok"]]
    if failed:
        validation["status"] = "fail"
        VALIDATION_FILE.write_text(
            json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        raise SystemExit(f"validation failed: {failed}")
    VALIDATION_FILE.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "target_sha256": target_sha,
                "labels_sha256": labels_sha,
                "script_sha256": script_sha,
                "output_sha256": output_sha,
                "rows": len(rows),
                "validation": validation["status"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
