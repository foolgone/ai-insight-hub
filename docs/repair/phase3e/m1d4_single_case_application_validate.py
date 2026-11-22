"""Validate and render the M1-D-4 v1.2.2 single-case diagnostic application."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
APP_FILE = BASE / "docs/repair/phase3e/m1d4-single-case-diagnostic-application.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.2/MANIFEST.json"
VALIDATION_FILE = BASE / "docs/repair/phase3e/m1d4-prompt-v1.2.2-validation.json"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.2"
OUT_MD = BASE / "docs/repair/38-m1d4-v1.2.2-single-case-diagnostic-application.md"
OUT_VALID = BASE / "docs/repair/phase3e/m1d4-single-case-application.validation.json"
OUT_VALID_MD = BASE / "docs/repair/phase3e/m1d4-single-case-application.validation.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d4-single-case-application.sha256"

CASE_IDS = ("Q23", "Q21", "Q11")
PROMPT_SHA = {
    "faithfulness.txt": "ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
MANIFEST_SHA = "81dd3a3219f6f2437b83264e1fd28d74db05c243e3335b9ce321bac9dbb22f5d"
VALIDATION_SHA = "fadef85639363bccf67e0052e0b36fcf780b970fb177d67d992f59c8b380e2f8"
TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
FIXTURE_SHA = "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"
REPAIR_SHA = "7541fe3f4d079f2c173ae6347a247b9614de14f30f761d216c1267bc4a591869"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def target_display(value: Any) -> str:
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
    validation_sha = sha256_bytes(VALIDATION_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    prompt_sha = {
        filename: sha256_bytes((PROMPT_DIR / filename).read_bytes()) for filename in PROMPT_SHA
    }
    meta = app["meta"]
    config = app["run_config"]
    budget = app["budget"]
    fixture = load_json(FIXTURE_FILE)
    fixture_cases = {case["id"]: case for case in fixture["cases"]}
    by_case = {case["case_id"]: case for case in app_cases}

    checks: list[dict[str, Any]] = [
        {"check": "status_pending", "ok": meta.get("status") == "pending_approval"},
        {"check": "not_approved", "ok": meta.get("not_approved") is True},
        {
            "check": "not_run",
            "ok": meta.get("judge_run") is False and app.get("judge_run") is False,
        },
        {
            "check": "not_activated",
            "ok": meta.get("runtime_activated") is False and app.get("runtime_activated") is False,
        },
        {"check": "scope_single_case", "ok": meta.get("scope") == "single_case_diagnostic"},
        {"check": "case_count_three", "ok": meta.get("case_count") == 3},
        {"check": "runs_per_case_one", "ok": meta.get("runs_per_case") == 1},
        {"check": "no_reuse", "ok": meta.get("not_reusing_previous_approval") is True},
        {"check": "prompt_version", "ok": meta.get("prompt_version") == "v1.2.2"},
        {"check": "prompt_frozen", "ok": meta.get("prompt_status") == "frozen"},
        {"check": "prompt_active_false", "ok": meta.get("prompt_active") is False},
        {"check": "prompt_sha", "ok": meta.get("prompt_sha256") == PROMPT_SHA},
        {"check": "prompt_files_match", "ok": prompt_sha == PROMPT_SHA},
        {"check": "manifest_sha", "ok": meta.get("manifest_sha256") == MANIFEST_SHA},
        {"check": "manifest_file_sha", "ok": manifest_sha == MANIFEST_SHA},
        {
            "check": "validation_sha",
            "ok": meta.get("validation_sha256") == VALIDATION_SHA
            and validation_sha == VALIDATION_SHA,
        },
        {"check": "rubric_v120", "ok": meta.get("rubric_version") == "v1.2.0"},
        {"check": "schema_v3", "ok": meta.get("schema_version") == "rag_judge_schema_v3"},
        {"check": "metric_v3", "ok": meta.get("metric_version") == "v3"},
        {"check": "default_v100", "ok": config.get("default_prompt_version") == "v1.0.0"},
        {"check": "target_sha", "ok": target_sha == TARGET_SHA},
        {"check": "labels_sha", "ok": labels_sha == LABELS_SHA},
        {"check": "fixture_sha", "ok": fixture_sha == FIXTURE_SHA},
        {
            "check": "fixture_cases_exist",
            "ok": all(case_id in fixture_cases for case_id in CASE_IDS),
        },
        {"check": "case_ids", "ok": tuple(case_ids) == CASE_IDS},
        {"check": "case_count_list", "ok": len(app_cases) == 3},
        {
            "check": "targets_match",
            "ok": all(
                case["targets"] == (targets[case["case_id"]].get("targets") or {})
                for case in app_cases
            ),
        },
        {
            "check": "groups_match_labels",
            "ok": all(
                case["group"] == labels[case["case_id"]]["group"]
                and case["final_category"] == labels[case["case_id"]]["final_category"]
                for case in app_cases
            ),
        },
        {
            "check": "q23_contract_assertions",
            "ok": by_case["Q23"]["acceptance"]["absence_claim"]
            == {
                "claim_type": "non_factual",
                "claim_subtype": "absence",
                "support_status": None,
                "evidence_refs": [],
            }
            and by_case["Q23"]["acceptance"]["primary"] == "contract_compliance"
            and by_case["Q23"]["acceptance"]["mixed_sentence_split"] is True
            and by_case["Q23"]["acceptance"]["no_placeholder_zero"] is True,
        },
        {
            "check": "q21_semantic_assertions",
            "ok": by_case["Q21"]["acceptance"]["primary"] == "semantic_support"
            and by_case["Q21"]["acceptance"]["exclusion_inference"] == "insufficient_evidence"
            and by_case["Q21"]["acceptance"]["f_status"] == "evaluated"
            and "semantic_pass_target_miss" in by_case["Q21"]["acceptance"]["target_miss_policy"],
        },
        {
            "check": "q11_regression_assertions",
            "ok": by_case["Q11"]["acceptance"]["primary"] == "regression"
            and by_case["Q11"]["acceptance"]["f_status"] == "evaluated"
            and by_case["Q11"]["acceptance"]["targets"] == targets["Q11"]["targets"],
        },
        {
            "check": "strict_not_judge_metric",
            "ok": "faithfulness_strict" not in config["judge_metrics"]
            and config["derived_metrics"] == ["faithfulness_strict"],
        },
        {
            "check": "agent_trace",
            "ok": meta.get("agent_commit") == "2ef9200"
            and meta.get("freeze_commit") == "159880b"
            and meta.get("repair_example_version") == "v1.2.2"
            and meta.get("repair_example_sha256") == REPAIR_SHA,
        },
        {
            "check": "execution_vehicle",
            "ok": "judge_trace" in config["execution_vehicle"]
            and "session=None" in config["execution_vehicle"]
            and "v1.2.2" in config["execution_vehicle"],
        },
        {
            "check": "service_path",
            "ok": config["service_path"]["entrypoint"] == "rag_judge_service.judge_trace"
            and config["service_path"]["session"] is None
            and config["service_path"]["creates_run"] is False
            and config["service_path"]["writes_db"] is False
            and config["service_path"]["uses_c3_scoring"] is True
            and config["service_path"]["driver_reimplements_scoring"] is False,
        },
        {
            "check": "synthetic_trace",
            "ok": config["synthetic_trace"]["fields"]["adapter"] == "fixture"
            and config["synthetic_trace"]["fields"]["mode"] == "query"
            and config["synthetic_trace"]["fields"]["context_source"] == "agent_chat"
            and config["synthetic_trace"]["fields"]["status"] == "success",
        },
        {
            "check": "no_side_effects",
            "ok": config.get("no_rag_call") is True
            and config.get("no_platform_run") is True
            and config.get("no_db_write") is True
            and config.get("no_weknora_call") is True
            and config.get("end_to_end") is False,
        },
        {
            "check": "budget",
            "ok": budget["primary_judge_calls"] == 9
            and budget["repair_reserve"] == 3
            and budget["retry_reserve"] == 2
            and budget["max_judge_calls"] == 14
            and budget["runs_per_case"] == 1
            and budget["ceiling_cny"] == 0.30,
        },
        {
            "check": "stop_conditions",
            "ok": {item["code"] for item in app["stop_conditions"]}
            == {
                "invalid_contract",
                "failed_execution",
                "q23_absence_contract",
                "q21_semantic_support_or_f_one",
                "q11_quote_or_target",
                "fingerprint_mismatch",
                "budget_ceiling",
                "unprocessed_case",
            },
        },
        {
            "check": "acceptance_assertions",
            "ok": len(app["acceptance_assertions"]) >= 20
            and any("Q23 absence" in item for item in app["acceptance_assertions"])
            and any("Q21 “质量问题不受 7 天限制”" in item for item in app["acceptance_assertions"])
            and any("Q11 quote" in item for item in app["acceptance_assertions"]),
        },
        {
            "check": "boundaries",
            "ok": any("不是 10 条，也不是 40 条" in item for item in app["boundaries"])
            and any("不激活 v1.2.2" in item for item in app["boundaries"])
            and any("不创建 RagEvaluationRun" in item for item in app["boundaries"])
            and any("不得跑 10/40" in item for item in app["boundaries"])
            and any("M1-C/M1-D 标 accepted" in item for item in app["boundaries"])
            and any("M2/M3" in item for item in app["boundaries"]),
        },
        {
            "check": "report_requirements",
            "ok": any("claim 级明细" in item for item in app["report_requirements"])
            and any("repair 轮" in item for item in app["report_requirements"])
            and any("prompt_version=v1.2.2" in item for item in app["report_requirements"])
            and any("不得写 accepted" in item for item in app["report_requirements"]),
        },
        {
            "check": "approval_items",
            "ok": len(app["approval_items"]) >= 10
            and any("Q23 契约" in item for item in app["approval_items"])
            and any("最多 14 calls" in item for item in app["approval_items"]),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    validation = {
        "name": "m1d4-single-case-diagnostic-application-validation",
        "kind": "static_application_validation_not_judge_run",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "application_sha256": app_sha,
        "target_sha256": target_sha,
        "labels_sha256": labels_sha,
        "manifest_sha256": manifest_sha,
        "validation_asset_sha256": validation_sha,
        "fixture_sha256": fixture_sha,
        "judge_run": False,
        "runtime_activated": False,
    }
    OUT_VALID.write_text(
        json.dumps(validation, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    validation_output_sha = sha256_bytes(OUT_VALID.read_bytes())

    lines = [
        "# M1-D-4 v1.2.2 单案例诊断申请（Q23 / Q21 / Q11）",
        "",
        "> 状态：`pending_approval`。**只申请 3 个案例、各 1 次；不是 10 条，也不是 40 条；未运行 Judge、未创建 Run、未激活。**",
        f"> application SHA：`{app_sha}`",
        f"> validation SHA：`{validation_output_sha}`",
        "> Prompt：`v1.2.2` / `frozen` / rubric `v1.2.0` / schema v3 / metric v3",
        f"> MANIFEST SHA：`{manifest_sha}`",
        f"> prompt validation SHA：`{validation_sha}`",
        f"> fixture SHA：`{fixture_sha}`",
        f"> target SHA：`{target_sha}`",
        "> 实现提交：`2ef9200`；冻结提交：`159880b`；repair SHA：`7541fe3f…`",
        "",
        "## 1. 申请范围",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| 类型 | 单案例诊断（诊断，不是验收样本） |",
        "| cases | `Q23`、`Q21`、`Q11` |",
        "| 每案例运行 | 1 次 × 3 指标 |",
        "| 主调用 | 9 |",
        "| repair reserve | 3 |",
        "| retry reserve | 2 |",
        "| 最大调用 | 14 |",
        "| 预计成本 / ceiling | CNY 0.10 / **0.30** |",
        "| 默认版本 | `v1.0.0` |",
        "| 批准状态 | **pending_approval，未批准** |",
        "",
        "固定边界：单案例结果只用于验证 v1.2.2 的 absence 与 evidence-directness 规则是否生效；不得替代 10 条，不得计入 10 条样本。",
        "",
        "## 2. 冻结资产与追溯",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| prompt_version | `v1.2.2` |",
        "| prompt_status / active | `frozen` / `false` |",
        "| F SHA | `ed21979a…` |",
        "| C SHA | `a50520de…` |",
        "| R SHA | `a5386070…` |",
        "| MANIFEST SHA | `81dd3a32…` |",
        "| prompt validation | `fadef856…`，23/23 pass |",
        "| rubric_version | `v1.2.0` |",
        "| Schema / Metric | `rag_judge_schema_v3` / `v3` |",
        "| target | `pilot-40-targets-v1.2.0-v1.0.2.json`，`3ee15dfc…` |",
        "| labels | `f139623f…` |",
        "| fixture | `pilot-10-v1.1.5-gate.json`，`dc7be14b…` |",
        "| agent_commit | `2ef9200` |",
        "| repair_example_version | `v1.2.2` |",
        "| repair_example_sha256 | `7541fe3f…` |",
        "",
        "## 3. 三个案例与验收",
        "",
        "| Case | group | category | context | F target | C target | R target | 验收重点 |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    focus = {
        "Q23": "契约合规：absence + 混合句拆分",
        "Q21": "语义支持：不得邻近规则硬撑",
        "Q11": "回归：连续 quote + 三项目标",
    }
    for case in app_cases:
        t = case["targets"]
        lines.append(
            f"| {case['case_id']} | {case['group']} | {case['final_category']} | "
            f"{case['context_count']} | {target_display(t.get('F'))} | "
            f"{target_display(t.get('C'))} | {target_display(t.get('R'))} | "
            f"{focus[case['case_id']]} |"
        )
    lines.extend(
        [
            "",
            "### 3.1 Q23 — 契约合规优先",
            "",
            "- F / F_strict 必须 `evaluated`，不得 `invalid`。",
            "- absence claim 必须是 `non_factual` + `absence` + "
            "`support_status=null` + `evidence_refs=[]`。",
            "- 禁止 `factual_claim + absence`；禁止给 absence 标 supported 或附 evidence。",
            "- 混合句必须拆分事实部分与 absence 部分。",
            "- F 报告是否落在 `[0.4, 0.5]`；不得调目标。",
            "- C / R 必须真实 `evaluated`，不得沿用上次 invalid 的 C=0.0 占位。",
            "- 再次 invalid，或 absence 仍 factual/supported → 诊断失败。",
            "",
            "### 3.2 Q21 — 语义支持优先，目标单独报",
            "",
            "- 涉及“质量问题不受 7 天限制”的 claim，必须 `insufficient_evidence`，或有直接写明该豁免的 quote。",
            "- 禁止用“运费由责任方承担”或“7 天内可换货”支持 7 天限制豁免。",
            "- 由排除项反推“普通商品适用”只能 `insufficient_evidence`。",
            "- F 必须 `evaluated`，不得 `invalid`。",
            "- 报告 F 是否落在 `[0.6, 0.7]`；语义通过但目标 miss → `semantic_pass_target_miss`，停止等人工复核。",
            "- 若 F 仍为 1.0 且仍用运费 quote 支持 7 天限制 → 诊断失败，不得本轮重跑。",
            "",
            "### 3.3 Q11 — 回归不倒退",
            "",
            "- F 必须 `evaluated`。",
            "- F ∈ `[0.6, 0.9]`，C ∈ `[0.8, 1.0]`，R ∈ `[0.9, 1.0]`。",
            "- quote 必须是单段连续原文，不得跨片段拼接。",
            "- 不得出现 `quote_not_found` 或其它 contract violation。",
            "",
            "## 4. 执行载体",
            "",
            "| 项 | 值 |",
            "|---|---|",
            "| execution_mode | `judge_only_fixture` |",
            "| Service entrypoint | `rag_judge_service.judge_trace` |",
            "| session / DB | `None` / 不写 DB |",
            "| adapter / top_k | 不适用 / 不适用 |",
            "| model / temperature / max_tokens | `qwen-max` / `0.0` / `8192` |",
            "| judge_prompt_version | `v1.2.2`，显式加载 |",
            "| default_prompt_version | `v1.0.0` |",
            "| synthetic trace | `adapter=fixture`、`mode=query`、"
            "`context_source=agent_chat`、`status=success`、"
            "`retrieved_contexts` 来自 fixture |",
            "| driver | 只汇总 `JudgeOutcome`，不重写 F 计分、不创建 Run |",
            "| WeKnora / RAG adapter | 不调用 |",
            "",
            "## 5. 预算",
            "",
            "| 项 | 值 |",
            "|---|---:|",
            "| 主运行 | 3 cases × 1 run × 3 metrics = 9 calls |",
            "| repair reserve | 3 |",
            "| retry reserve | 2 |",
            "| 最大调用 | 14 |",
            "| 预计成本 | CNY 0.10 |",
            "| 硬上限 | **CNY 0.30** |",
            "| 计数规则 | 所有 Judge 模型调用都计入，包括 repair 与 retry |",
            "",
            "## 6. 停止条件",
            "",
            "任一命中即停止，保留已完成结果，不得中途改 Prompt/Agent/fixture 重跑。",
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
            "## 7. 输出要求",
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
            "单案例未运行；10/40 未批准；v1.2.2 未激活。",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    md_sha = sha256_bytes(OUT_MD.read_bytes())
    OUT_SHA.write_text(
        f"{app_sha}  m1d4-single-case-diagnostic-application.json\n"
        f"{validation_output_sha}  m1d4-single-case-application.validation.json\n"
        f"{md_sha}  {OUT_MD.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    OUT_VALID_MD.write_text(
        "\n".join(
            [
                "# M1-D-4 v1.2.2 单案例申请校验",
                "",
                f"- status：`{validation['status']}`",
                f"- checks：{len(checks)} / failed {len(failed)}",
                f"- application SHA：`{app_sha}`",
                f"- validation SHA：`{validation_output_sha}`",
                "- 未运行 Judge；未创建 Run；未写 DB；未激活。",
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
                "validation_sha256": validation_output_sha,
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
