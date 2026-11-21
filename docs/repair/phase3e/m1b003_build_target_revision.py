"""Build the M1-B-003 metadata-only target revision (v1.0.2).

Reads the frozen v1.0.1 target table, copies all 40 target rows unchanged,
adds the dual-metric metadata, and writes a NEW file. The old file is never
overwritten.

Run:
    python docs/repair/phase3e/m1b003_build_target_revision.py
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD_FILE = BASE / "pilot-40-targets-v1.2.0.json"
NEW_FILE = BASE / "pilot-40-targets-v1.2.0-v1.0.2.json"
SHA_FILE = BASE / "pilot-40-targets-v1.2.0-v1.0.2.sha256"
VALIDATION_FILE = BASE / "pilot-40-targets-v1.2.0-v1.0.2.validation.json"
OLD_SHA = "34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb"
FINAL_LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def main() -> None:
    old_bytes = OLD_FILE.read_bytes()
    old_sha = sha256_bytes(old_bytes)
    if old_sha != OLD_SHA:
        raise SystemExit(f"old target SHA mismatch: {old_sha} != {OLD_SHA}")

    old = json.loads(old_bytes)
    if old["meta"].get("row_count") != 40 or len(old["cases"]) != 40:
        raise SystemExit("old target row count is not 40")

    new = {
        "meta": copy.deepcopy(old["meta"]),
        "cases": copy.deepcopy(old["cases"]),
    }
    meta = new["meta"]
    meta.update(
        {
            "status": "freeze_draft_pending_human",
            "revision": "v1.0.2",
            "revision_note": (
                "v1.0.2 metadata-only revision: add dual-metric target metadata; "
                "all 40 target values unchanged from v1.0.1; old v1.0.1 file/SHA is not overwritten."
            ),
            "drafted_at": "2026-11-19",
            "draft_prepared_by": "Agent",
            "supersedes_file": OLD_FILE.name,
            "supersedes_sha256": OLD_SHA,
            "target_values_changed": False,
            "f_target_metric": "faithfulness",
            "f_target_denominator": "S+U+I",
            "f_target_denominator_long": "supported_plus_unsupported_plus_insufficient",
            "f_target_display": "Faithfulness（证据覆盖）",
            "f_strict_metric": "faithfulness_strict",
            "f_strict_role": "diagnostic",
            "f_strict_target": None,
            "f_strict_display": "Strict Faithfulness（可判定事实）",
            "metric_version": "v3",
            "schema_version": "rag_judge_schema_v3",
            "runtime_active": False,
            "not_for_run": True,
            "sha256_file": SHA_FILE.name,
            "note": (
                "M1-B-003 freeze draft; not accepted; not for runtime. "
                "Target values are identical to v1.0.1; only metric metadata was added."
            ),
        }
    )
    # Keep the old provenance fields but make the new file self-describing.
    meta["old_targets_status"] = "read_only"
    meta["q32_precondition"] = old["meta"]["q32_precondition"]

    new_bytes = (json.dumps(new, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    NEW_FILE.write_bytes(new_bytes)
    new_sha = sha256_bytes(new_bytes)
    SHA_FILE.write_text(f"{new_sha}  {NEW_FILE.name}\n", encoding="utf-8", newline="\n")

    # Verify target values are deep-equal to the old file.
    values_equal = all(
        old_case.get("targets") == new_case.get("targets")
        for old_case, new_case in zip(old["cases"], new["cases"])
    )
    ids = [case["case_id"] for case in new["cases"]]
    expected_ids = [f"Q{i:02d}" for i in range(1, 41)]
    checks = [
        ("row_count_40", len(new["cases"]) == 40, len(new["cases"])),
        ("unique_case_ids", len(ids) == len(set(ids)), len(set(ids))),
        ("all_case_ids_q01_q40", ids == expected_ids, "Q01-Q40"),
        ("target_values_identical_to_v1_0_1", values_equal, values_equal),
        ("f_target_metric", meta["f_target_metric"] == "faithfulness", meta["f_target_metric"]),
        ("f_target_denominator", meta["f_target_denominator"] == "S+U+I", meta["f_target_denominator"]),
        (
            "f_target_denominator_long",
            meta["f_target_denominator_long"] == "supported_plus_unsupported_plus_insufficient",
            meta["f_target_denominator_long"],
        ),
        ("f_strict_metric", meta["f_strict_metric"] == "faithfulness_strict", meta["f_strict_metric"]),
        ("f_strict_role", meta["f_strict_role"] == "diagnostic", meta["f_strict_role"]),
        ("f_strict_target_null", meta["f_strict_target"] is None, meta["f_strict_target"]),
        ("target_values_changed_false", meta["target_values_changed"] is False, meta["target_values_changed"]),
        ("supersedes_sha256_matches_old", meta["supersedes_sha256"] == OLD_SHA, meta["supersedes_sha256"]),
        ("old_file_sha_unchanged", sha256_file(OLD_FILE) == OLD_SHA, sha256_file(OLD_FILE)),
        ("runtime_active_false", meta["runtime_active"] is False, meta["runtime_active"]),
        ("not_for_run_true", meta["not_for_run"] is True, meta["not_for_run"]),
        ("status_freeze_draft_pending_human", meta["status"] == "freeze_draft_pending_human", meta["status"]),
        ("revision_v1_0_2", meta["revision"] == "v1.0.2", meta["revision"]),
        ("final_labels_sha_unchanged", meta["final_labels_sha256"] == FINAL_LABELS_SHA, meta["final_labels_sha256"]),
        ("q32_precondition_present", bool(meta.get("q32_precondition")), True),
        ("sha256_file_contains_new_sha", SHA_FILE.read_text(encoding="utf-8").startswith(new_sha), new_sha),
    ]
    validation = {
        "file": NEW_FILE.name,
        "sha256": new_sha,
        "sha256_file": SHA_FILE.name,
        "supersedes_file": OLD_FILE.name,
        "supersedes_sha256": OLD_SHA,
        "row_count": len(new["cases"]),
        "revision": meta["revision"],
        "status": meta["status"],
        "checks": [
            {"name": name, "ok": bool(ok), "detail": detail}
            for name, ok, detail in checks
        ],
        "all_pass": all(ok for _, ok, _ in checks),
    }
    VALIDATION_FILE.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(
        {
            "new_file": NEW_FILE.name,
            "new_sha256": new_sha,
            "old_sha256": old_sha,
            "checks": len(checks),
            "all_pass": validation["all_pass"],
        },
        ensure_ascii=False,
        indent=1,
    ))


if __name__ == "__main__":
    main()
