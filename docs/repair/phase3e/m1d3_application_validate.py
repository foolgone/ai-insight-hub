"""Validate and render the M1-D-3 v1.2.1 10-case Judge application."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
APP_FILE = BASE / "docs/repair/phase3e/m1d3-ten-case-application.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.1/MANIFEST.json"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
OUT_MD = BASE / "docs/repair/33-m1d3-ten-case-judge-application.md"
OUT_VALID = BASE / "docs/repair/phase3e/m1d3-ten-case-application.validation.json"
OUT_VALID_MD = BASE / "docs/repair/phase3e/m1d3-ten-case-application.validation.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d3-ten-case-application.sha256"

CASE_IDS = ("Q01", "Q04", "Q11", "Q17", "Q21", "Q23", "Q29", "Q31", "Q35", "Q36")
PROMPT_SHA = {
    "faithfulness.txt": "9efdc64df1eebafa727bc0946a03192c2d9e9907bd7a3170f867f19774211068",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
MANIFEST_SHA = "8bdd673cd44ed772dfc1630280e571d4cdd8ed786066eb72eb553a9be8b0b278"
TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
FIXTURE_SHA = "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def target_display(value: Any) -> str:
    if value == "skipped":
        return "skipped"
    if isinstance(value, list) and len(value) == 2:
        if value[0] == value[1]:
            return f"{value[0]:.1f}"
        return f"{value[0]:.1f}–{value[1]:.1f}"
    return "—"


def main() -> None:
    app = load_json(APP_FILE)
    target_data = load_json(TARGET_FILE)
    labels_data = load_json(LABELS_FILE)
    targets = {case["case_id"]: case for case in target_data["cases"]}
    labels = {case["case_id"]: case for case in labels_data["labels"]}
    app_cases = app["cases"]
    case_ids = [case["case_id"] for case in app_cases]
    app_sha = sha256_bytes(APP_FILE.read_bytes())
    target_sha = sha256_bytes(TARGET_FILE.read_bytes())
    labels_sha = sha256_bytes(LABELS_FILE.read_bytes())
    manifest_sha = sha256_bytes(MANIFEST_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    meta = app["meta"]
    config = app["run_config"]
    budget = app["budget"]

    checks: list[dict[str, Any]] = [
        {"check": "status_pending", "ok": meta.get("status") == "pending_approval"},
        {"check": "not_approved", "ok": meta.get("not_approved") is True},
        {"check": "not_run", "ok": app.get("judge_run") is False},
        {"check": "not_activated", "ok": app.get("runtime_activated") is False},
        {"check": "no_reuse", "ok": meta.get("not_reusing_previous_approval") is True},
        {"check": "prompt_version", "ok": meta.get("prompt_version") == "v1.2.1"},
        {"check": "prompt_frozen", "ok": meta.get("prompt_status") == "frozen"},
        {"check": "prompt_active_false", "ok": meta.get("prompt_active") is False},
        {"check": "prompt_sha", "ok": meta.get("prompt_sha256") == PROMPT_SHA},
        {"check": "manifest_sha", "ok": manifest_sha == MANIFEST_SHA},
        {"check": "rubric_v120", "ok": meta.get("rubric_version") == "v1.2.0"},
        {"check": "schema_v3", "ok": meta.get("schema_version") == "rag_judge_schema_v3"},
        {"check": "metric_v3", "ok": meta.get("metric_version") == "v3"},
        {"check": "default_v100", "ok": config.get("default_prompt_version") == "v1.0.0"},
        {"check": "target_sha", "ok": target_sha == TARGET_SHA},
        {"check": "labels_sha", "ok": labels_sha == LABELS_SHA},
        {"check": "fixture_sha", "ok": fixture_sha == FIXTURE_SHA},
        {"check": "case_count", "ok": len(app_cases) == 10},
        {"check": "case_ids", "ok": tuple(case_ids) == CASE_IDS},
        {
            "check": "targets_match",
            "ok": all(
                case["targets"] == (targets[case["case_id"]].get("targets") or {})
                for case in app_cases
            ),
        },
        {
            "check": "labels_match",
            "ok": all(
                case["group"] == labels[case["case_id"]]["group"]
                and case["final_category"] == labels[case["case_id"]]["final_category"]
                and case["baseline_status"] == labels[case["case_id"]]["baseline_status"]
                for case in app_cases
            ),
        },
        {
            "check": "execution_vehicle",
            "ok": "judge_trace" in config["execution_vehicle"]
            and "session=None" in config["execution_vehicle"]
            and "v1.2.1" in config["execution_vehicle"],
        },
        {
            "check": "service_path",
            "ok": config["service_path"]["entrypoint"] == "rag_judge_service.judge_trace"
            and config["service_path"]["uses_c3_scoring"] is True
            and config["service_path"]["driver_reimplements_scoring"] is False
            and config["service_path"]["creates_run"] is False
            and config["service_path"]["writes_db"] is False,
        },
        {
            "check": "synthetic_trace",
            "ok": config["synthetic_trace"]["fields"]["adapter"] == "fixture"
            and config["synthetic_trace"]["fields"]["mode"] == "query"
            and config["synthetic_trace"]["fields"]["context_source"] == "agent_chat"
            and config["synthetic_trace"]["fields"]["status"] == "success",
        },
        {
            "check": "q11_bad",
            "ok": meta["q11_evidence"]["bad"]["expected"]
            == {
                "status": "invalid",
                "invalid_reason": "contract_violation",
                "error_code": "quote_not_found",
            },
        },
        {
            "check": "q11_good",
            "ok": meta["q11_evidence"]["good"]["expected"] == {"status": "evaluated", "score": 1.0},
        },
        {
            "check": "budget",
            "ok": budget["primary_judge_calls"] == 30
            and budget["max_judge_calls"] == 51
            and budget["estimated_cost_cny"]["ceiling"] == 1.0,
        },
        {
            "check": "q36_dual",
            "ok": app["q36_c_policy"]["mode"] == "dual_report_diagnostic"
            and app["q36_c_policy"]["no_post_hoc_selection"] is True,
        },
        {
            "check": "hg_repeat",
            "ok": budget["repeat_policy"]["runs_per_case"] == 3
            and budget["repeat_policy"]["cases"] == ["Q23", "Q35", "Q36"],
        },
        {
            "check": "stop_conditions",
            "ok": {item["code"] for item in app["stop_conditions"]}
            >= {
                "preflight_failure",
                "invalid_contract",
                "failed_execution",
                "q29_not_skipped",
                "budget_ceiling",
                "q11_quote_continuity",
            },
        },
        {
            "check": "boundaries",
            "ok": any("不复用" in item for item in app["boundaries"])
            and any("40" in item for item in app["boundaries"]),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    validation = {
        "name": "m1d3-ten-case-application-validation",
        "kind": "static_application_validation_not_judge_run",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "application_sha256": app_sha,
        "target_sha256": target_sha,
        "labels_sha256": labels_sha,
        "manifest_sha256": manifest_sha,
        "fixture_sha256": fixture_sha,
        "judge_run": False,
        "runtime_activated": False,
    }
    OUT_VALID.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    validation_sha = sha256_bytes(OUT_VALID.read_bytes())

    lines = [
        "# M1-D-3 v1.2.1 10 条 Judge 申请",
        "",
        "> 状态：`pending_approval`。**新申请，不复用 v1.2.0 批准；未运行 Judge、未创建 Run、未激活。**",
        f"> application SHA：`{app_sha}`",
        f"> validation SHA：`{validation_sha}`",
        "> Prompt：`v1.2.1` / `frozen` / rubric `v1.2.0` / schema v3 / metric v3",
        f"> MANIFEST SHA：`{manifest_sha}`",
        f"> fixture SHA：`{fixture_sha}`",
        f"> target SHA：`{target_sha}`",
        "",
        "## 1. 冻结资产",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| prompt_version | `v1.2.1` |",
        "| F SHA | `9efdc64d…` |",
        "| C SHA | `a50520de…` |",
        "| R SHA | `a5386070…` |",
        "| MANIFEST SHA | `8bdd673c…` |",
        "| rubric_version | `v1.2.0` |",
        "| Schema / Metric | `rag_judge_schema_v3` / `v3` |",
        "| target | `pilot-40-targets-v1.2.0-v1.0.2.json` |",
        "| 默认版本 | `v1.0.0` |",
        "",
        "## 2. 10 个 Cases",
        "",
        "| Case | group | category | context | baseline | "
        "F target | C target | R target | known issue |",
        "|---|---|---|---:|---|---|---|---|---|",
    ]
    for case in app_cases:
        t = case["targets"]
        lines.append(
            f"| {case['case_id']} | {case['group']} | {case['final_category']} | "
            f"{case['context_count']} | {case['baseline_status']} | "
            f"{target_display(t.get('F'))} | {target_display(t.get('C'))} | "
            f"{target_display(t.get('R'))} | {case['known_issue'] or '—'} |"
        )
    lines.extend(
        [
            "",
            "固定口径：Q29 F 必须 `skipped(no_scorable_claims)`；"
            "Q35/Q36 用 fixture 固定旧 run 输入；Q36 C 双报不参与 PASS/FAIL。",
            "",
            "## 3. 执行载体",
            "",
            "| 项 | 值 |",
            "|---|---|",
            "| execution_mode | `judge_only_fixture` |",
            "| Service entrypoint | `rag_judge_service.judge_trace` |",
            "| session / DB | `None` / 不写 DB |",
            "| adapter / top_k | 不适用 / 不适用 |",
            "| model / temperature / max_tokens | `qwen-max` / `0.0` / `8192` |",
            "| judge_prompt_version | `v1.2.1` |",
            "| default_prompt_version | `v1.0.0` |",
            "| synthetic trace | `adapter=fixture`、`mode=query`、"
            "`context_source=agent_chat`、`status=success`、"
            "`retrieved_contexts` 来自 fixture |",
            "| driver | 只汇总 `JudgeOutcome`，不重写 F 计分、不创建 Run |",
            "",
            "## 4. Q11 修复证据",
            "",
            "| 项 | 结果 |",
            "|---|---|",
            "| bad 非连续 quote | `invalid(contract_violation)` + `quote_not_found` |",
            "| good 精确 claim + 连续 quote | `evaluated 1.0` |",
            "| tests | `test_v121_bad_noncontiguous_quote_is_invalid` / "
            "`test_v121_good_contiguous_quote_is_supported` |",
            "| fixture | `dc7be14b…`；未改 fixture |",
            "",
            "## 5. 预算 / 重复 / Q36",
            "",
            "| 项 | 值 |",
            "|---|---:|",
            "| 主运行 | 10 cases × 3 = 30 calls |",
            "| HG 重复 | Q23/Q35/Q36 固定 3 次；Q23 3/3、Q35/Q36 ≥2/3 |",
            "| 计划调用 | 48 |",
            "| 执行重试 reserve | 3 |",
            "| 最大调用 | 51 |",
            "| 预计成本 / 上限 / ceiling | CNY 0.45 / 0.760 / **1.00** |",
            "| Q36 C | base 0.5–0.6 与 variant 0.9–1.0 双报，只作诊断 |",
            "",
            "## 6. 停止条件",
            "",
            "| code | 条件 |",
            "|---|---|",
        ]
    )
    for item in app["stop_conditions"]:
        lines.append(f"| `{item['code']}` | {item['condition']} |")
    lines.extend(
        [
            "",
            "## 7. 报告要求",
            "",
            *[f"- {item}" for item in app["report_requirements"]],
            "",
            "## 8. 边界",
            "",
            *[f"- {item}" for item in app["boundaries"]],
            "",
            "## 9. 批准清单",
            "",
            *[f"- [ ] {item}" for item in app["approval_items"]],
            "",
            "10 条未运行；40 条未批准；v1.2.1 未激活。",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    md_sha = sha256_bytes(OUT_MD.read_bytes())
    OUT_SHA.write_text(
        f"{app_sha}  m1d3-ten-case-application.json\n"
        f"{validation_sha}  m1d3-ten-case-application.validation.json\n"
        f"{md_sha}  {OUT_MD.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    OUT_VALID_MD.write_text(
        "\n".join(
            [
                "# M1-D-3 v1.2.1 申请校验",
                "",
                f"- status：`{validation['status']}`",
                f"- checks：{len(checks)} / failed {len(failed)}",
                f"- application SHA：`{app_sha}`",
                f"- validation SHA：`{validation_sha}`",
                "- 未运行 Judge；未创建 Run；未激活。",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": validation["status"],
                "checks": len(checks),
                "failed": len(failed),
                "application_sha256": app_sha,
                "validation_sha256": validation_sha,
                "md_sha256": md_sha,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if failed:
        raise SystemExit(f"validation failed: {failed}")


if __name__ == "__main__":
    main()
