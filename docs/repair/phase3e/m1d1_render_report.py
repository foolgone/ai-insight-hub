"""Render M1-D-1 result report from the raw Judge-only results (no Judge call)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
APPLICATION_FILE = BASE / "docs/repair/phase3e/m1d1-ten-case-application.json"
RAW_FILE = BASE / "docs/repair/phase3e/m1d1-judge-only-results.json"
OUT_MD = BASE / "docs/repair/29-m1d1-judge-only-results.md"
OUT_SUMMARY = BASE / "docs/repair/phase3e/m1d1-judge-only-summary.json"
OUT_SHA = BASE / "docs/repair/phase3e/m1d1-judge-only-report.sha256"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def in_target(value: Any, target: Any) -> bool:
    if value is None or not isinstance(target, list) or len(target) != 2:
        return False
    return float(target[0]) <= float(value) <= float(target[1])


def outcome(by_name: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    return by_name.get(name) or {}


def display(outcome_data: dict[str, Any]) -> str:
    if not outcome_data:
        return "—"
    if outcome_data.get("status") == "invalid":
        return "invalid"
    if outcome_data.get("status") == "failed":
        return "failed"
    if outcome_data.get("status") == "skipped":
        return f"skipped({outcome_data.get('skipped_reason')})"
    value = outcome_data.get("score")
    return "—" if value is None else f"{float(value):.6f}"


def target_status(app_case: dict[str, Any], raw_case: dict[str, Any] | None) -> str:
    if raw_case is None:
        return "NOT_RUN"
    runs = raw_case.get("runs") or []
    if not runs:
        return "BLOCKED"
    for run in runs:
        by_name = {o["metric_name"]: o for o in run["outcomes"]}
        if any(
            by_name.get(metric, {}).get("status") in {"invalid", "failed"}
            for metric in ("faithfulness", "answer_correctness", "answer_relevancy")
        ):
            return "BLOCKED"
    case_id = app_case["case_id"]
    targets = app_case["targets"]
    if case_id == "Q29":
        f = outcome({o["metric_name"]: o for o in runs[0]["outcomes"]}, "faithfulness")
        if f.get("status") != "skipped" or f.get("skipped_reason") != "no_scorable_claims":
            return "FAIL"
        for metric in ("answer_correctness", "answer_relevancy"):
            by_name = {o["metric_name"]: o for o in runs[0]["outcomes"]}
            if not in_target(outcome(by_name, metric).get("score"), targets.get(metric)):
                return "FAIL"
        return "PASS"
    for target_metric in ("faithfulness", "answer_correctness", "answer_relevancy"):
        if target_metric not in targets:
            continue
        if case_id == "Q36" and target_metric == "answer_correctness":
            continue
        pass_count = 0
        for run in runs:
            by_name = {o["metric_name"]: o for o in run["outcomes"]}
            if in_target(outcome(by_name, target_metric).get("score"), targets[target_metric]):
                pass_count += 1
        required = 3 if case_id == "Q23" else (2 if case_id in {"Q35", "Q36"} else 1)
        if pass_count < required:
            return "FAIL"
    return "PASS"


def main() -> None:
    application = load_json(APPLICATION_FILE)
    raw = load_json(RAW_FILE)
    raw_sha = sha256_bytes(RAW_FILE.read_bytes())
    app_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    cases_by_id = {case["case_id"]: case for case in raw.get("cases", [])}

    rows: list[dict[str, Any]] = []
    for app_case in application["cases"]:
        case_id = app_case["case_id"]
        raw_case = cases_by_id.get(case_id)
        runs = (raw_case or {}).get("runs") or []
        by_name = {o["metric_name"]: o for o in runs[0]["outcomes"]} if runs else {}
        rows.append(
            {
                "case_id": case_id,
                "group": app_case["group"],
                "targets": app_case["targets"],
                "attempted": raw_case is not None,
                "runs": len(runs),
                "status": "not_run" if raw_case is None else "attempted",
                "target_pass": target_status(app_case, raw_case),
                "F": display(outcome(by_name, "faithfulness")),
                "F_strict": display(outcome(by_name, "faithfulness_strict")),
                "C": display(outcome(by_name, "answer_correctness")),
                "R": display(outcome(by_name, "answer_relevancy")),
            }
        )

    invalid_details: list[dict[str, Any]] = []
    for raw_case in raw.get("cases", []):
        for run in raw_case.get("runs", []):
            for item in run.get("outcomes", []):
                if item.get("status") in {"invalid", "failed"}:
                    invalid_details.append(
                        {
                            "case_id": raw_case["case_id"],
                            "run": run["run_index"],
                            "metric": item["metric_name"],
                            "status": item["status"],
                            "invalid_reason": item.get("invalid_reason"),
                            "error_type": item.get("error_type"),
                            "errors": (item.get("details") or {}).get("validation_errors"),
                        }
                    )

    unprocessed = [row["case_id"] for row in rows if not row["attempted"]]
    attempted = [row["case_id"] for row in rows if row["attempted"]]
    summary = {
        "name": "m1d1-judge-only-summary",
        "kind": "derived_summary_from_raw_results_not_judge_run",
        "status": raw["meta"]["status"],
        "verified": raw["meta"].get("verified", False),
        "stop_triggered": raw.get("stop_triggered"),
        "stop_reason": raw.get("stop_reason"),
        "gate": raw.get("gate"),
        "attempted_cases": attempted,
        "unprocessed_cases": unprocessed,
        "invalid_details": invalid_details,
        "cases": rows,
        "totals": raw.get("totals"),
        "raw_results_sha256": raw_sha,
        "application_sha256": app_sha,
        "fixture_sha256": raw["meta"].get("fixture_sha256"),
        "manifest_sha256": raw["meta"].get("manifest_sha256"),
        "target_sha256": raw["meta"].get("target_sha256"),
        "created_run": False,
        "wrote_db": False,
        "runtime_activated": False,
        "default_prompt_version": raw["meta"].get("default_prompt_version"),
    }
    OUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    summary_sha = sha256_bytes(OUT_SUMMARY.read_bytes())
    OUT_SHA.write_text(
        f"{summary_sha}  {OUT_SUMMARY.name}\n"
        f"{sha256_bytes(OUT_MD.read_bytes()) if OUT_MD.exists() else 'pending'}  {OUT_MD.name}\n",
        encoding="utf-8",
        newline="\n",
    )

    lines = [
        "# M1-D-1 Judge-only Production Service replay 结果（停止）",
        "",
        "> 状态：`stopped`；在 Q11 的 F `invalid(contract_violation)` 处按停止条件停止。",
        "> **已停止，不重跑、不改 Prompt、不跑剩余 cases、不跑 40。**",
        "> 未创建 Run、未写 DB、未调用 WeKnora、未激活 v1.2.0。",
        f"> application SHA：`{app_sha}`",
        f"> raw results SHA：`{raw_sha}`",
        f"> summary SHA：`{summary_sha}`",
        f"> fixture SHA：`{raw['meta'].get('fixture_sha256')}`",
        f"> MANIFEST SHA：`{raw['meta'].get('manifest_sha256')}`",
        "",
        "## 1. 10 条逐条状态",
        "",
        "| Case | group | F | F_strict | C | R | 结果 | target |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['group']} | {row['F']} | {row['F_strict']} | "
            f"{row['C']} | {row['R']} | {row['status']} | {row['target_pass']} |"
        )
    lines.extend(
        [
            "",
            "## 2. 停止条件与 Q11 invalid",
            "",
            f"- stop_triggered：`{raw.get('stop_triggered')}`",
            f"- stop_reason：{raw.get('stop_reason')}",
            "- 停止条件命中：`invalid(contract_violation)`；按批准规则立即停止。",
            "",
        ]
    )
    for item in invalid_details:
        lines.extend(
            [
                f"### {item['case_id']} run {item['run']} / {item['metric']}",
                "",
                f"- status：`{item['status']}`",
                f"- invalid_reason：`{item['invalid_reason']}`",
                f"- error_type：`{item['error_type']}`",
                f"- validation_errors：`{json.dumps(item['errors'], ensure_ascii=False)}`",
                "",
            ]
        )
    lines.extend(
        [
            "Q11 的直接原因：F 输出中 `evidence_refs.quote` 不是 C1 的逐字连续子串。",
            "Service 按 v3 契约判整条 F invalid；`faithfulness_strict` 同步 invalid；未进入目标判定。",
            "",
            "## 3. 未处理 cases",
            "",
            f"- attempted：{attempted}",
            f"- unprocessed：{unprocessed}",
            "- HG Q23/Q35/Q36：未运行，因此没有三次结果、median/min/max 或 Q36 C base/variant。",
            "",
            "## 4. 分类计数",
            "",
            "| 类别 | 值 |",
            "|---|---:|",
            "| attempted cases | 3 |",
            "| unprocessed cases | 7 |",
            "| invalid | 1（Q11 F；strict 同步 invalid） |",
            "| failed | 0 |",
            "| skipped | 0（Q29 未到达） |",
            "",
            "## 5. 调用与成本",
            "",
            "| 项 | 实际 | 预算/上限 |",
            "|---|---:|---:|",
            f"| case-runs | {raw['totals']['case_runs']} | 16 |",
            f"| Judge calls | {raw['totals']['judge_calls']} | 51 |",
            f"| input tokens | {raw['totals']['input_tokens']} | 198,900 |",
            f"| output tokens | {raw['totals']['output_tokens']} | 29,410 |",
            f"| cost CNY | {raw['totals']['cost_cny']:.6f} | 1.00 |",
            f"| preflight tokens | {raw['totals']['preflight_input_tokens']} / "
            f"{raw['totals']['preflight_output_tokens']} | — |",
            "",
            "## 6. 结论",
            "",
            "- M1-D-1 状态：`blocked`；**未 verified**，更未 accepted。",
            "- 10 条闸门未通过；剩余 7 条未运行。",
            "- 不申请 40 条；不激活 v1.2.0；不启动 M2/M3。",
            "- 下一步只能由人工决定：复审 Q11 quote 契约问题、是否允许修复后重新申请。",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    OUT_SHA.write_text(
        f"{summary_sha}  {OUT_SUMMARY.name}\n"
        f"{sha256_bytes(OUT_MD.read_bytes())}  {OUT_MD.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "verified": summary["verified"],
                "attempted": attempted,
                "unprocessed": unprocessed,
                "summary_sha256": summary_sha,
                "md_sha256": sha256_bytes(OUT_MD.read_bytes()),
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
