"""Validate the M1-B-003-r1 freeze draft contract text.

This is a static text validation only: no runtime code, no Judge, no DB.
It also writes the freeze draft SHA256 and validation JSON.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
DRAFT = BASE.parent / "19-m1b-003-freeze-draft.md"
SHA_FILE = BASE.parent / "19-m1b-003-freeze-draft.sha256"
VALIDATION_FILE = BASE.parent / "19-m1b-003-freeze-draft.validation.json"
OLD_TARGET = BASE / "pilot-40-targets-v1.2.0.json"
NEW_TARGET = BASE / "pilot-40-targets-v1.2.0-v1.0.2.json"
FINAL_LABELS = BASE / "pilot-40-final-labels.json"
OLD_TARGET_SHA = "34357b34c3d0fc85e78f90eeebb353b25a148926e3a55b19f17cc23b08b2b5eb"
NEW_TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
FINAL_LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_touched_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=BASE.parent.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        raw = line[3:].strip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.replace("\\", "/"))
    return paths


def main() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    draft_sha = sha256_file(DRAFT)
    SHA_FILE.write_text(f"{draft_sha}  19-m1b-003-freeze-draft.md\n", encoding="utf-8", newline="\n")

    touched = git_touched_paths()
    runtime_touched = [
        p for p in touched
        if p.startswith(("backend/", "frontend/", "nginx/", "ops/"))
    ]
    r2_record = BASE.parent / "21-m1b-003-r2-revision-record.md"
    r2_text = r2_record.read_text(encoding="utf-8") if r2_record.exists() else ""
    checks = [
        ("unsupported_not_contradiction", "不等于 contradiction" in text and "未被上下文支持" in text, True),
        ("fstrict_explanation", "`F_strict=1.0` 的正确解释" in text and "不表示" in text and "无 unsupported" in text, True),
        ("no_active_contradiction_or_mixed", "| `contradiction_or_mixed` |" not in text, True),
        ("contains_unsupported_claims_label", "| 6 | `contains_unsupported_claims` |" in text, True),
        ("run_config_immutable", "Run 配置不可变" in text and "Prompt / Schema / 模型 / 检索配置" in text, True),
        ("retry_is_child_run", "重试 = 新建子 Run" in text and "逐字段一致" in text, True),
        ("unique_key_reviewed", "(run_id, dataset_item_id, metric_name, metric_version)" in text and "保留，不新增列" in text, True),
        ("item_level_status", all(x in text for x in ["Item 级状态", "`evaluated`", "`skipped`", "`invalid`", "`failed`", "`invalid_items`"]), True),
        ("case_count_not_row_count", "指标行数 ≠ Case 数" in text, True),
        ("completed_items_semantics", "`completed_items` | **等于 `evaluated_items`**" in text and "不代表所有终态 Item" in text, True),
        ("item_status_mutually_exclusive", "互斥且完整覆盖" in text and "恰好属于一类" in text, True),
        ("conservation_relation", "total_items = evaluated_items + invalid_items + failed_items + skipped_items + unprocessed_items" in text, True),
        ("cross_metric_example", "3 个 item" in text and "metric rows = 6" in text and "Case 数 = 3" in text, True),
        ("invalid_persistence_contract", "独立 `invalid` 状态" in text and "failed + invalid_reason" in text and "聚合层看到 `invalid_reason` 必须归类 invalid" in text, True),
        ("invalid_metric_counts", "invalid_results = (status = invalid)" in text and "failed_results  = (status = failed)" in text, True),
        ("invalid_not_in_mean", "invalid row 不进入指标均值" in text, True),
        ("invalid_not_execution_failure", "invalid 不得被解释为模型执行失败" in text, True),
        ("r2_two_items_closed", "r2（2 项收尾）" in text and "Item 级计数语义不完整" in text and "invalid 持久化契约不清" in text, True),
        ("unified_terminology", "统一展示术语" in text and "contains_insufficient_claims" in text and "评测覆盖率" in text and "证据不足比例" in text, True),
        ("d1_d4_formulas_unchanged", "F_strict   = S / (S + U)" in text and "F_coverage = S / (S + U + I)" in text, True),
        ("d1_display_names_unchanged", "Faithfulness（证据覆盖）" in text and "Strict Faithfulness（可判定事实）" in text, True),
        ("d3_all_insufficient_unchanged", "| `faithfulness` | `evaluated 0.0`" in text and "| `faithfulness_strict` | `skipped(no_decidable_claims)`" in text, True),
        ("d4_observation_fields_unchanged", all(x in text for x in ["| `faithfulness_strict` | `S/(S+U)`", "`unsupported_ratio`", "`insufficient_ratio`", "`strict_gap`", "不设 `F_strict` 目标"]), True),
        ("target_shas_unchanged", "3ee15dfc" in text and "34357b34" in text, True),
        ("status_pending_not_accepted", "freeze_draft_pending_human" in text and "未 accepted" in text, True),
        ("four_issues_closed", all(x in text for x in ["4 项关闭", "`F_strict=1.0` 被解释为", "`contradiction_or_mixed` 等标签不准确", "Run 配置/重试/唯一约束不清", "双 Metric Row 的 Item 聚合不清"]), True),
        ("revision_record_referenced", "21-m1b-003-r2-revision-record.md" in text, True),
        ("revision_record_exists", r2_record.exists(), True),
        ("revision_record_sha_matches", draft_sha in r2_text, True),
        ("no_runtime_changes", not runtime_touched, runtime_touched),
        ("old_target_sha_unchanged", sha256_file(OLD_TARGET) == OLD_TARGET_SHA, sha256_file(OLD_TARGET)),
        ("new_target_sha_unchanged", sha256_file(NEW_TARGET) == NEW_TARGET_SHA, sha256_file(NEW_TARGET)),
        ("final_labels_sha_unchanged", sha256_file(FINAL_LABELS) == FINAL_LABELS_SHA, sha256_file(FINAL_LABELS)),
    ]
    validation = {
        "file": DRAFT.name,
        "sha256": draft_sha,
        "sha256_file": SHA_FILE.name,
        "status": "freeze_draft_pending_human",
        "revision": "M1-B-003-r2",
        "checks": [{"name": n, "ok": bool(ok), "detail": d} for n, ok, d in checks],
        "all_pass": all(ok for _, ok, _ in checks),
    }
    VALIDATION_FILE.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(
        {"sha256": draft_sha, "checks": len(checks), "all_pass": validation["all_pass"]},
        ensure_ascii=False,
        indent=1,
    ))


if __name__ == "__main__":
    main()
