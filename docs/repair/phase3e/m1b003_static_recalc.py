"""Static recalculation for M1-B-003 (F_strict / F_coverage).

This is NOT a Judge run. It reads the already-recorded v1.1.5 40-case results,
recomputes S/U/I buckets and the two F metrics, and writes a reproducible
artifact with input/script/output SHA256.

Run:
    python docs/repair/phase3e/m1b003_static_recalc.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
INPUT_FILE = BASE / "pilot-40-v1.0.0-vs-v1.1.5.json"
TARGET_FILE = BASE / "pilot-40-targets-v1.2.0-v1.0.2.json"
OUTPUT_FILE = BASE / "m1b003-static-recalc.json"
SHA_FILE = BASE / "m1b003-static-recalc.sha256"
MD_FILE = BASE / "m1b003-static-recalc.md"

# Explicit v1.2.0 expected conversions. These are NOT observed v1.1.5 labels.
# They are kept separate so expected values never get mixed with observed values.
EXPECTED_CONVERSIONS = {
    "Q17": {
        "delta": {"I": 1, "N": -1},
        "basis": "v1.2.0 expected: cl5 policy_relationship factual/insufficient; v1.1.5 cl5 was meta",
    },
    "Q32": {
        "delta": {"I": -1, "N": 1},
        "basis": "v1.2.0 expected: cl1 uncertainty non_factual; v1.1.5 cl1 was factual/insufficient",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def round6(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def counts_from_outcome(outcome: dict[str, Any]) -> dict[str, int]:
    claims = (outcome.get("details") or {}).get("claims") or []
    counts = {"S": 0, "U": 0, "I": 0, "N": 0}
    for claim in claims:
        claim_type = claim.get("claim_type")
        status = claim.get("support_status")
        if claim_type == "non_factual":
            counts["N"] += 1
        elif claim_type == "factual_claim":
            if status == "supported":
                counts["S"] += 1
            elif status == "unsupported":
                counts["U"] += 1
            elif status == "insufficient_evidence":
                counts["I"] += 1
    return counts


def compute(counts: dict[str, int]) -> dict[str, Any]:
    s, u, i = counts["S"], counts["U"], counts["I"]
    if s + u > 0:
        strict_status = "evaluated"
        strict = round6(s / (s + u))
    else:
        strict_status = "skipped(no_decidable_claims)"
        strict = None
    if s + u + i > 0:
        coverage_status = "evaluated"
        coverage = round6(s / (s + u + i))
    else:
        coverage_status = "skipped(no_scorable_claims)"
        coverage = None
    all_insufficient = s == 0 and u == 0 and i > 0
    return {
        "F_strict": strict,
        "F_coverage": coverage,
        "F_strict_status": strict_status,
        "F_coverage_status": coverage_status,
        "all_insufficient": all_insufficient,
        "unsupported_count": u,
        "insufficient_count": i,
        "insufficient_ratio": round6(i / (s + u + i)) if (s + u + i) > 0 else None,
        "unsupported_ratio": round6(u / (s + u + i)) if (s + u + i) > 0 else None,
    }


def target_pass(coverage: float | None, target_f: Any) -> str:
    if coverage is None:
        return "skip"
    if not isinstance(target_f, list) or len(target_f) != 2:
        return "no_target"
    low, high = float(target_f[0]), float(target_f[1])
    if low <= coverage <= high:
        return "in"
    return "above" if coverage > high else "below"


def apply_expected(counts: dict[str, int], case_id: str) -> tuple[dict[str, int], str | None]:
    conversion = EXPECTED_CONVERSIONS.get(case_id)
    if conversion is None:
        return counts, None
    expected = dict(counts)
    for bucket, delta in conversion["delta"].items():
        expected[bucket] += delta
        if expected[bucket] < 0:
            raise SystemExit(f"{case_id} expected conversion makes {bucket} negative")
    return expected, conversion["basis"]


def main() -> None:
    input_bytes = INPUT_FILE.read_bytes()
    input_sha = sha256_bytes(input_bytes)
    target_bytes = TARGET_FILE.read_bytes()
    target_sha = sha256_bytes(target_bytes)
    script_sha = sha256_file(Path(__file__))

    input_data = json.loads(input_bytes)
    target_data = json.loads(target_bytes)
    targets = {case["case_id"]: case.get("targets", {}).get("F") for case in target_data["cases"]}
    target_case_ids = [f"Q{i:02d}" for i in range(1, 41)]

    by_id = {case["id"]: case for case in input_data["cases"]}
    rows: list[dict[str, Any]] = []
    for case_id in target_case_ids:
        case = by_id.get(case_id)
        target_f = targets.get(case_id)
        if case is None:
            rows.append(
                {
                    "case_id": case_id,
                    "target_F": target_f,
                    "observed": {"status": "not_run", "reason": "Q33-Q40 not run in v1.1.5"},
                    "expected_v1.2.0": None,
                }
            )
            continue

        outcome = next(
            (item for item in case.get("arms", {}).get("v1.1.5", {}).get("outcomes", []) if item.get("metric") == "faithfulness"),
            None,
        )
        if outcome is None:
            rows.append(
                {
                    "case_id": case_id,
                    "target_F": target_f,
                    "observed": {"status": "not_run", "reason": "no v1.1.5 faithfulness outcome"},
                    "expected_v1.2.0": None,
                }
            )
            continue

        status = outcome.get("status")
        if status != "evaluated":
            rows.append(
                {
                    "case_id": case_id,
                    "target_F": target_f,
                    "observed": {
                        "status": status,
                        "skipped_reason": outcome.get("skipped_reason"),
                        "error": outcome.get("error"),
                        "F_coverage": None,
                        "F_strict": None,
                    },
                    "expected_v1.2.0": None,
                }
            )
            continue

        counts = counts_from_outcome(outcome)
        metrics = compute(counts)
        expected_counts, expected_basis = apply_expected(counts, case_id)
        expected_metrics = compute(expected_counts) if expected_basis else None
        rows.append(
            {
                "case_id": case_id,
                "target_F": target_f,
                "observed": {
                    "status": "evaluated",
                    "old_F": round6(outcome.get("score")),
                    "counts": counts,
                    **metrics,
                    "target_pass": target_pass(metrics["F_coverage"], target_f),
                },
                "expected_v1.2.0": (
                    {
                        "is_expected": True,
                        "not_observed": True,
                        "basis": expected_basis,
                        "counts": expected_counts,
                        **expected_metrics,
                        "target_pass": target_pass(expected_metrics["F_coverage"], target_f),
                    }
                    if expected_metrics is not None
                    else None
                ),
            }
        )

    output = {
        "meta": {
            "name": "m1b003-static-recalc",
            "kind": "static_recalculation_not_judge_run",
            "generated_on": "2026-11-19",
            "input_file": INPUT_FILE.name,
            "input_sha256": input_sha,
            "target_file": TARGET_FILE.name,
            "target_sha256": target_sha,
            "script_file": Path(__file__).name,
            "script_sha256": script_sha,
            "row_count": len(rows),
            "definitions": {
                "F_strict": "S / (S + U)",
                "F_coverage": "S / (S + U + I)",
                "S": "factual_claim + supported",
                "U": "factual_claim + unsupported",
                "I": "factual_claim + insufficient_evidence",
                "N": "non_factual",
            },
            "expected_conversions": {
                case_id: {
                    "is_expected": True,
                    "not_observed": True,
                    "basis": payload["basis"],
                    "delta": payload["delta"],
                }
                for case_id, payload in EXPECTED_CONVERSIONS.items()
            },
            "q32_note": "Q32 expected_v1.2.0 is an expected conversion, not an observed v1.1.5 result. Do not mix with observed values.",
            "q17_note": "Q17 expected_v1.2.0 is an expected conversion, not an observed v1.1.5 result. Do not mix with observed values.",
            "not_for_runtime": True,
        },
        "cases": rows,
    }
    output_bytes = (json.dumps(output, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    OUTPUT_FILE.write_bytes(output_bytes)
    output_sha = sha256_bytes(output_bytes)
    SHA_FILE.write_text(f"{output_sha}  {OUTPUT_FILE.name}\n", encoding="utf-8", newline="\n")

    # Markdown summary (kept in sync with the JSON by construction).
    lines = [
        "# M1-B-003 静态重算（非 Judge 运行）",
        "",
        f"> 状态：`static_recalculation_not_judge_run`；生成日期 2026-11-19。",
        f"> 输入：`{INPUT_FILE.name}` SHA256 `{input_sha}`",
        f"> 目标：`{TARGET_FILE.name}` SHA256 `{target_sha}`",
        f"> 脚本：`{Path(__file__).name}` SHA256 `{script_sha}`",
        f"> 输出：`{OUTPUT_FILE.name}` SHA256 `{output_sha}`",
        "",
        "## 定义",
        "",
        "- `F_strict = S / (S + U)`",
        "- `F_coverage = S / (S + U + I)`",
        "- `S/U/I/N`：factual supported / factual unsupported / factual insufficient / non_factual",
        "",
        "## 关键案例",
        "",
        "| Case | target | old F | F_strict | F_coverage | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    key_cases = {"Q11", "Q17", "Q21", "Q23", "Q32", "Q14", "Q29"}
    for row in rows:
        if row["case_id"] not in key_cases:
            continue
        observed = row.get("observed", {})
        expected = row.get("expected_v1.2.0")
        if observed.get("status") == "evaluated":
            lines.append(
                f"| {row['case_id']} | {row['target_F']} | {observed.get('old_F')} | "
                f"{observed.get('F_strict')} | {observed.get('F_coverage')} | observed v1.1.5 |"
            )
        else:
            lines.append(
                f"| {row['case_id']} | {row['target_F']} | — | — | — | {observed.get('status')} |"
            )
        if expected:
            lines.append(
                f"| {row['case_id']}（预期） | {row['target_F']} | — | {expected.get('F_strict')} | "
                f"{expected.get('F_coverage')} | expected v1.2.0；{expected.get('basis')} |"
            )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本文件是静态重算，不是 Judge 新运行；",
            "- Q17/Q32 的 `expected_v1.2.0` 是预期转换，不是已观测结果；",
            "- 未修改 Prompt/Service/Schema/API/DB；",
            "- 未创建/激活 v1.2.0；未运行 Judge。",
        ]
    )
    MD_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(
        {
            "input_sha256": input_sha,
            "target_sha256": target_sha,
            "script_sha256": script_sha,
            "output_sha256": output_sha,
            "rows": len(rows),
        },
        ensure_ascii=False,
        indent=1,
    ))


if __name__ == "__main__":
    main()
