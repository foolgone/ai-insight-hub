"""M1-C C4 static target regression (NOT a Judge run).

Reads the frozen v1.0.2 target table, final labels, and the existing
m1b003 static recalculation. It verifies Q11/Q17/Q21/Q23/Q32 and writes
SHA/validation artifacts.

Run:
    python docs/repair/phase3e/m1c_c4_static_targets.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
TARGET_FILE = BASE / "pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "pilot-40-final-labels.json"
RECALC_FILE = BASE / "m1b003-static-recalc.json"
OUTPUT_FILE = BASE / "m1c-c4-static-targets.json"
MD_FILE = BASE / "m1c-c4-static-targets.md"
SHA_FILE = BASE / "m1c-c4-static-targets.sha256"
VALIDATION_FILE = BASE / "m1c-c4-static-targets.validation.json"

TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
RECALC_SHA = "53787fbb2a434953354bd821b62581e6e56ba5db10751149c236f1e7656437bb"

CASES = ("Q11", "Q17", "Q21", "Q23", "Q32")
EXPECTED_SOURCE = {"Q17": "expected_v1.2.0", "Q32": "expected_v1.2.0"}
OBSERVED_SOURCE = {
    "Q11": "observed_v1.1.5",
    "Q21": "observed_v1.1.5",
    "Q23": "observed_v1.1.5",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def round6(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def target_pass(value: float | None, target: Any) -> str:
    if value is None:
        return "skip"
    if not isinstance(target, list) or len(target) != 2:
        return "no_target"
    low, high = float(target[0]), float(target[1])
    if low <= value <= high:
        return "in"
    return "above" if value > high else "below"


def main() -> None:
    target_bytes = TARGET_FILE.read_bytes()
    labels_bytes = LABELS_FILE.read_bytes()
    recalc_bytes = RECALC_FILE.read_bytes()
    target_sha = sha256_bytes(target_bytes)
    labels_sha = sha256_bytes(labels_bytes)
    recalc_sha = sha256_bytes(recalc_bytes)
    script_sha = sha256_file(Path(__file__))

    target_data = json.loads(target_bytes)
    labels_data = json.loads(labels_bytes)
    recalc_data = json.loads(recalc_bytes)
    target_by_id = {case["case_id"]: case for case in target_data["cases"]}
    recalc_by_id = {case["case_id"]: case for case in recalc_data["cases"]}
    labels_by_id = {case["case_id"]: case for case in labels_data["labels"]}

    rows: list[dict[str, Any]] = []
    for case_id in CASES:
        target = target_by_id[case_id]
        recalc = recalc_by_id[case_id]
        label = labels_by_id[case_id]
        target_f = target.get("targets", {}).get("F")
        if case_id in EXPECTED_SOURCE:
            observed = recalc.get("expected_v1.2.0")
            source = EXPECTED_SOURCE[case_id]
            if not observed:
                raise SystemExit(f"{case_id} expected_v1.2.0 missing")
            not_observed = True
            basis = observed.get("basis")
        else:
            observed = recalc.get("observed")
            source = OBSERVED_SOURCE[case_id]
            if not observed or observed.get("status") != "evaluated":
                raise SystemExit(f"{case_id} observed v1.1.5 missing/not evaluated")
            not_observed = False
            basis = None

        coverage = round6(observed.get("F_coverage"))
        strict = round6(observed.get("F_strict"))
        rows.append(
            {
                "case_id": case_id,
                "group": label.get("group"),
                "final_category": label.get("final_category"),
                "target_F": target_f,
                "source": source,
                "not_observed": not_observed,
                "basis": basis,
                "F_coverage": coverage,
                "F_strict": strict,
                "F_coverage_status": observed.get("F_coverage_status"),
                "F_strict_status": observed.get("F_strict_status"),
                "all_insufficient": observed.get("all_insufficient"),
                "insufficient_count": observed.get("insufficient_count"),
                "insufficient_ratio": round6(observed.get("insufficient_ratio")),
                "target_pass": target_pass(coverage, target_f),
            }
        )

    output = {
        "meta": {
            "name": "m1c-c4-static-targets",
            "kind": "static_target_regression_not_judge_run",
            "generated_on": "2026-11-20",
            "target_file": TARGET_FILE.name,
            "target_sha256": target_sha,
            "target_revision": target_data["meta"].get("revision"),
            "labels_file": LABELS_FILE.name,
            "labels_sha256": labels_sha,
            "recalc_file": RECALC_FILE.name,
            "recalc_sha256": recalc_sha,
            "script_file": Path(__file__).name,
            "script_sha256": script_sha,
            "row_count": len(rows),
            "q17_note": "Q17 uses expected v1.2.0 labels, not observed Judge output.",
            "q32_note": "Q32 uses expected v1.2.0 labels, not observed Judge output.",
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
        "# M1-C C4 静态目标回归（非 Judge 运行）",
        "",
        "> 状态：`static_target_regression_not_judge_run`；生成日期 2026-11-20。",
        f"> 目标：`{TARGET_FILE.name}` SHA256 `{target_sha}`",
        f"> 分类：`{LABELS_FILE.name}` SHA256 `{labels_sha}`",
        f"> 重算：`{RECALC_FILE.name}` SHA256 `{recalc_sha}`",
        f"> 脚本：`{Path(__file__).name}` SHA256 `{script_sha}`",
        f"> 输出：`{OUTPUT_FILE.name}` SHA256 `{output_sha}`",
        "",
        "| Case | target F | source | F_coverage | F_strict | target |",
        "|---|---:|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['target_F']} | {row['source']} | "
            f"{row['F_coverage']} | {row['F_strict']} | {row['target_pass']} |"
        )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本文件是静态目标回归，不是 Judge 新运行；",
            "- Q17/Q32 使用 `expected_v1.2.0`，不是实测；",
            "- Q11/Q21/Q23 使用 `observed_v1.1.5`；",
            "- F_strict 只记录，不作为目标通过率；",
            "- 未修改 Prompt/Service/Schema/API/DB；未运行 Judge。",
        ]
    )
    MD_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    validation = {
        "name": "m1c-c4-static-targets-validation",
        "status": "pass",
        "checks": [
            {"check": "target_sha256", "ok": target_sha == TARGET_SHA},
            {"check": "labels_sha256", "ok": labels_sha == LABELS_SHA},
            {"check": "recalc_sha256", "ok": recalc_sha == RECALC_SHA},
            {"check": "row_count", "ok": len(rows) == 5},
            {
                "check": "q17_expected",
                "ok": rows[1]["source"] == "expected_v1.2.0"
                and rows[1]["not_observed"],
            },
            {
                "check": "q32_expected",
                "ok": rows[4]["source"] == "expected_v1.2.0"
                and rows[4]["not_observed"],
            },
            {
                "check": "q11_observed",
                "ok": rows[0]["source"] == "observed_v1.1.5"
                and not rows[0]["not_observed"],
            },
            {
                "check": "q21_observed",
                "ok": rows[2]["source"] == "observed_v1.1.5"
                and not rows[2]["not_observed"],
            },
            {
                "check": "q23_observed",
                "ok": rows[3]["source"] == "observed_v1.1.5"
                and not rows[3]["not_observed"],
            },
            {
                "check": "all_target_in",
                "ok": all(row["target_pass"] == "in" for row in rows),
            },
            {"check": "q17_coverage", "ok": rows[1]["F_coverage"] == 0.8},
            {"check": "q32_coverage", "ok": rows[4]["F_coverage"] == 1.0},
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
                "recalc_sha256": recalc_sha,
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
