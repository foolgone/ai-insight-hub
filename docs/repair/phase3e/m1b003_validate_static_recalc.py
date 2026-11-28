"""Validate the M1-B-003 static recalculation artifact.

Reads the generated JSON + .sha256 and writes a validation JSON.
This does not run Judge and does not modify the recalculation output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUTPUT_FILE = BASE / "m1b003-static-recalc.json"
SHA_FILE = BASE / "m1b003-static-recalc.sha256"
VALIDATION_FILE = BASE / "m1b003-static-recalc.validation.json"

INPUT_SHA = "29732088952ad406d296b2c7d8fd5d34f427fd1e703b9818e2bebf80374a5c68"
TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    output_bytes = OUTPUT_FILE.read_bytes()
    output_sha = sha256_bytes(output_bytes)
    sha_text = SHA_FILE.read_text(encoding="utf-8").strip()
    data = json.loads(output_bytes)
    cases = data["cases"]
    meta = data["meta"]
    observed = [c for c in cases if c["observed"].get("status") == "evaluated"]
    not_run = [c for c in cases if c["observed"].get("status") == "not_run"]
    skipped = [c for c in cases if c["observed"].get("status") == "skipped"]
    coverage_matches = [
        c for c in observed
        if c["observed"].get("old_F") is not None
        and c["observed"].get("F_coverage") is not None
        and abs(float(c["observed"]["old_F"]) - float(c["observed"]["F_coverage"])) <= 1e-6
    ]
    q17 = next(c for c in cases if c["case_id"] == "Q17")
    q32 = next(c for c in cases if c["case_id"] == "Q32")
    q14 = next(c for c in cases if c["case_id"] == "Q14")
    q29 = next(c for c in cases if c["case_id"] == "Q29")

    checks = [
        ("output_sha_matches_sha_file", sha_text.split()[0] == output_sha, output_sha),
        ("row_count_40", len(cases) == 40, len(cases)),
        ("observed_evaluated_30", len(observed) == 30, len(observed)),
        ("observed_total_32", len(observed) + len(skipped) == 32, len(observed) + len(skipped)),
        ("not_run_count_8", len(not_run) == 8, len(not_run)),
        ("skipped_count_2", len(skipped) == 2, len(skipped)),
        ("input_sha_matches", meta.get("input_sha256") == INPUT_SHA, meta.get("input_sha256")),
        ("target_sha_matches", meta.get("target_sha256") == TARGET_SHA, meta.get("target_sha256")),
        ("q17_expected_separated", bool((q17.get("expected_v1.2.0") or {}).get("is_expected")) and bool((q17.get("expected_v1.2.0") or {}).get("not_observed")) and abs(float(q17["expected_v1.2.0"]["F_coverage"]) - 0.8) <= 1e-9, q17["expected_v1.2.0"].get("F_coverage")),
        ("q32_expected_separated", bool((q32.get("expected_v1.2.0") or {}).get("is_expected")) and bool((q32.get("expected_v1.2.0") or {}).get("not_observed")) and abs(float(q32["expected_v1.2.0"]["F_coverage"]) - 1.0) <= 1e-9, q32["expected_v1.2.0"].get("F_coverage")),
        ("q14_context_unavailable", q14["observed"].get("skipped_reason") == "context_unavailable", q14["observed"].get("skipped_reason")),
        ("q29_no_scorable", q29["observed"].get("skipped_reason") == "no_scorable_claims", q29["observed"].get("skipped_reason")),
        ("coverage_matches_old_f_30", len(coverage_matches) == 30, len(coverage_matches)),
    ]
    validation = {
        "file": OUTPUT_FILE.name,
        "sha256": output_sha,
        "sha256_file": SHA_FILE.name,
        "kind": meta.get("kind"),
        "row_count": len(cases),
        "checks": [{"name": n, "ok": bool(ok), "detail": d} for n, ok, d in checks],
        "all_pass": all(ok for _, ok, _ in checks),
    }
    VALIDATION_FILE.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"checks": len(checks), "all_pass": validation["all_pass"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
