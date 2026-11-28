"""Render M1-D-3 results from raw Judge-only results (no Judge call)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
APPLICATION_FILE = BASE / "docs/repair/phase3e/m1d3-ten-case-application.json"
RAW_FILE = BASE / "docs/repair/phase3e/m1d3-judge-only-results.json"
OUT_MD = BASE / "docs/repair/34-m1d3-judge-only-results.md"
OUT_SUMMARY = BASE / "docs/repair/phase3e/m1d3-judge-only-summary.json"
OUT_SHA = BASE / "docs/repair/phase3e/m1d3-judge-only-report.sha256"
CASE_IDS = ("Q01", "Q04", "Q11", "Q17", "Q21", "Q23", "Q29", "Q31", "Q35", "Q36")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def in_target(value: Any, target: Any) -> bool:
    if value is None or not isinstance(target, list) or len(target) != 2:
        return False
    return float(target[0]) <= float(value) <= float(target[1])


def display(outcome: dict[str, Any] | None) -> str:
    if not outcome:
        return "—"
    status = outcome.get("status")
    if status in {"invalid", "failed", "skipped"}:
        reason = outcome.get("invalid_reason") or outcome.get("skipped_reason")
        return f"{status}({reason})" if reason else status
    score = outcome.get("score")
    return "—" if score is None else f"{float(score):.6f}"


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
        by_name = {o["metric_name"]: o for o in runs[0]["outcomes"]}
        f = by_name.get("faithfulness", {})
        if f.get("status") != "skipped" or f.get("skipped_reason") != "no_scorable_claims":
            return "FAIL"
        for metric, key in (("answer_correctness", "C"), ("answer_relevancy", "R")):
            if not in_target(by_name.get(metric, {}).get("score"), targets.get(key)):
                return "FAIL"
        return "PASS"

    for target_metric, key in (
        ("faithfulness", "F"),
        ("answer_correctness", "C"),
        ("answer_relevancy", "R"),
    ):
        if key not in targets:
            continue
        if case_id == "Q36" and target_metric == "answer_correctness":
            continue
        pass_count = 0
        for run in runs:
            by_name = {o["metric_name"]: o for o in run["outcomes"]}
            if in_target(by_name.get(target_metric, {}).get("score"), targets[key]):
                pass_count += 1
        required = 3 if case_id == "Q23" else (2 if case_id in {"Q35", "Q36"} else 1)
        if pass_count < required:
            return "FAIL"
    return "PASS"


def main() -> None:
    app = load_json(APPLICATION_FILE)
    raw = load_json(RAW_FILE)
    app_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    raw_sha = sha256_bytes(RAW_FILE.read_bytes())
    raw_cases = {case["case_id"]: case for case in raw.get("cases", [])}
    app_cases = {case["case_id"]: case for case in app["cases"]}

    rows: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        app_case = app_cases[case_id]
        raw_case = raw_cases.get(case_id)
        runs = (raw_case or {}).get("runs") or []
        by_name = {o["metric_name"]: o for o in runs[0]["outcomes"]} if runs else {}
        rows.append(
            {
                "case_id": case_id,
                "group": app_case["group"],
                "targets": app_case["targets"],
                "attempted": raw_case is not None,
                "runs": len(runs),
                "F": display(by_name.get("faithfulness")),
                "F_strict": display(by_name.get("faithfulness_strict")),
                "C": display(by_name.get("answer_correctness")),
                "R": display(by_name.get("answer_relevancy")),
                "target": target_status(app_case, raw_case),
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
                            "error_message": item.get("error_message"),
                            "errors": (item.get("details") or {}).get("errors"),
                        }
                    )

    attempted = [row["case_id"] for row in rows if row["attempted"]]
    unprocessed = [row["case_id"] for row in rows if not row["attempted"]]
    summary = {
        "name": "m1d3-judge-only-summary",
        "kind": "derived_summary_from_raw_results_not_judge_run",
        "status": raw["meta"]["status"],
        "verified": raw["meta"].get("verified", False),
        "stop_triggered": raw.get("stop_triggered"),
        "stop_reason": raw.get("stop_reason"),
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

    lines = [
        "# M1-D-3 v1.2.1 Judge-only Production Service replay 结果（停止）",
        "",
        "> 状态：`stopped`；在 Q23 F `invalid(contract_violation)` 处按停止条件停止。",
        "> **已停止，不重跑、不改 Prompt、不跑剩余 cases、不跑 40。**",
        "> 未创建 Run、未写 DB、未调用 WeKnora、未激活 v1.2.1。",
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
            f"{row['C']} | {row['R']} | "
            f"{'attempted' if row['attempted'] else 'not_run'} | {row['target']} |"
        )
    lines.extend(
        [
            "",
            "## 2. 停止原因与 invalid",
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
                f"- error_message：{item['error_message'] or '—'}",
                f"- errors：`{json.dumps(item['errors'], ensure_ascii=False)}`",
                "",
            ]
        )
    q23 = raw_cases.get("Q23")
    if q23:
        f = next(
            (o for o in q23["runs"][0]["outcomes"] if o["metric_name"] == "faithfulness"),
            None,
        )
        original = ((f or {}).get("details") or {}).get("original_raw_output") or ""
        if original:
            lines.extend(
                [
                    "Q23 原始 F 输出的关键契约问题（摘要）：",
                    "",
                    "- 出现 `claim_type=factual_claim` + `claim_subtype=absence`；",
                    "- 出现 `support_status=supported` 但 `evidence_refs=[]`；",
                    "- 结构化输出修复后仍不合法 → `StructuredOutputError` → `invalid(contract_violation)`。",
                    "",
                ]
            )
    lines.extend(
        [
            "## 3. HG 三次结果",
            "",
            "| Case | runs | F | F_strict | C | R | 说明 |",
            "|---|---:|---:|---:|---:|---:|---|",
            "| Q23 | 1 | invalid | invalid | 0.000000 | 0.900000 | 首轮 invalid，未继续 3 次 |",
            "| Q35 | 0 | — | — | — | — | unprocessed |",
            "| Q36 | 0 | — | — | — | — | unprocessed |",
            "",
            "Q23 只有 1 次结果，不能计算 median/min/max；Q35/Q36 未运行。",
            "",
            "## 4. Q36 C base/variant",
            "",
            "Q36 未运行，因此没有 C actual / base / variant 结果；未做 post-hoc 选择。",
            "",
            "## 5. 分类计数",
            "",
            "| 类别 | 值 |",
            "|---|---:|",
            "| attempted cases | 6 |",
            "| unprocessed cases | 4 |",
            "| invalid | Q23 F；strict 同步 invalid |",
            "| failed | 0 |",
            "| skipped | 0（Q29 未到达） |",
            "",
            "## 6. 调用与成本",
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
            "## 7. 结论",
            "",
            "- M1-D-3 状态：`blocked`；未 verified，更未 accepted。",
            "- Q11 已通过（F=0.8，目标 0.6–0.9）；Q17 F=0.8（目标 0.7–0.9）通过。",
            "- Q21 F=1.0，超出目标 0.6–0.7；如继续执行会 target FAIL，但本轮因 Q23 invalid 先停止。",
            "- Q23 F invalid，10 条闸门未通过；Q29/Q31/Q35/Q36 未运行。",
            "- 不申请 40 条；不激活 v1.2.1；不启动 M2/M3。",
            "",
            "## 8. 边界",
            "",
            "- 通过 `rag_judge_service.judge_trace(session=None, ...)` 执行；",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora；",
            "- 未激活 v1.2.1、未改默认版本/Prompt；",
            "- 未跑 40、未启动 M2/M3；",
            "- verified：`False`；accepted 仍需人工决定。",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    md_sha = sha256_bytes(OUT_MD.read_bytes())
    OUT_SHA.write_text(
        f"{summary_sha}  {OUT_SUMMARY.name}\n" f"{md_sha}  {OUT_MD.name}\n",
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
                "md_sha256": md_sha,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
