"""Build the M1-D-1 10-case Judge application (NOT a Judge run).

Reads the frozen target table, final labels, and frozen v1.2.0 prompt
manifest. Writes a machine-readable application, a human-readable
application document, SHA256, and a static validation file.

Run:
    python docs/repair/phase3e/m1d1_ten_case_application.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.0/MANIFEST.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.0"
OUT_MD = BASE / "docs/repair/28-m1d1-ten-case-judge-application.md"
OUT_JSON = BASE / "docs/repair/phase3e/m1d1-ten-case-application.json"
OUT_VALIDATION = BASE / "docs/repair/phase3e/m1d1-ten-case-application.validation.json"
OUT_SHA = BASE / "docs/repair/phase3e/m1d1-ten-case-application.sha256"

TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
MANIFEST_SHA = "ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778"
PROMPT_SHA = {
    "faithfulness.txt": "b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
CASE_IDS = ("Q01", "Q04", "Q11", "Q17", "Q21", "Q23", "Q29", "Q31", "Q35", "Q36")
FROZEN_COMMIT = "df036a8"
FREEZE_RECORD = "docs/repair/27-m1d0-prompt-freeze-record.md"
REPORT_TEMPLATE = "docs/repair/phase3e/m1c-c4-report-template.md"

RUN_CONFIG: dict[str, Any] = {
    "execution_mode": "query",
    "adapter": "weknora",
    "dataset": "pilot-40 frozen test split (same dataset version as v1.1.5 pilot)",
    "dataset_version_id": "captured at run creation; item_ids resolved from item_key",
    "dataset_checksum": "captured in run config_snapshot; report must include it",
    "split": "test",
    "limit": 10,
    "top_k": 5,
    "precision_mode": "at_k",
    "judge_metrics": ["faithfulness", "answer_correctness", "answer_relevancy"],
    "derived_metrics": ["faithfulness_strict"],
    "judge_prompt_version": "v1.2.0",
    "default_prompt_version": "v1.0.0",
    "model": "qwen-max",
    "temperature": 0.0,
    "max_tokens": 8192,
    "soft_budget_seconds": 1500,
    "schema_version": "rag_judge_schema_v3",
    "metric_version": "v3",
    "weknora": {
        "knowledge_base_id": "4ae8e147-6f76-4330-93f1-d2b3fef3d9ba",
        "agent_id": ("existing deployment value; snapshot at run; do not commit secrets"),
        "tenant_id": ("existing deployment value; snapshot at run; do not commit secrets"),
    },
    "llm_endpoint": (
        "existing DashScope-compatible endpoint used by prior qwen-max gates; " "no key in repo"
    ),
    "env_scope": (
        "process-local for this Run only; do not write to repo/.env; " "restore after Run"
    ),
    "env": {
        "DEFAULT_LLM_MODEL": "qwen-max",
        "DEFAULT_TEMPERATURE": "0.0",
        "RAG_JUDGE_MAX_TOKENS": "8192",
        "RAG_ADAPTER": "weknora",
        "RAG_JUDGE_PROMPT_VERSION": "v1.0.0",
    },
}

BUDGET: dict[str, Any] = {
    "primary_case_runs": 10,
    "primary_judge_calls": 30,
    "conditional_repeat_cases": ["Q23", "Q35", "Q36"],
    "conditional_repeat_extra_case_runs": 6,
    "max_case_runs": 16,
    "max_judge_calls": 48,
    "estimated_input_tokens": [70000, 160000],
    "estimated_output_tokens": [9000, 26000],
    "estimated_cost_cny": {
        "expected": 0.35,
        "upper": 0.60,
        "ceiling": 0.80,
    },
    "price_basis": (
        "qwen-max public price: input CNY 0.0024/1K, output CNY 0.0096/1K; "
        "actual bill is authoritative"
    ),
    "note": (
        "No 40-case spend; ceiling includes one execution retry and HG repeats, "
        "not repeated prompt tuning"
    ),
}

STOP_CONDITIONS: list[dict[str, str]] = [
    {
        "code": "preflight_failure",
        "condition": (
            "WeKnora 配置/健康检查、LLM endpoint/model、dataset version、"
            "10 个 item_ids、Prompt/MANIFEST SHA 或 22/22 validation 任一不满足"
        ),
        "action": "拒绝创建 Run；不得跳过 preflight",
    },
    {
        "code": "invalid_contract",
        "condition": (
            "任一 case/metric 出现 invalid(contract_violation)，包括 "
            "schema/subtype/evidence/quote/conflict 违约"
        ),
        "action": "立即停止；保留已完成结果；不得改 Prompt 或放宽契约后重跑",
    },
    {
        "code": "failed_execution",
        "condition": "任一 case/metric 出现 failed(execution)",
        "action": "同配置最多重试一次；再次失败立即停止",
    },
    {
        "code": "hg_supported_quote_invalid",
        "condition": "Q23/Q35/Q36 任一 supported claim 的 quote 非逐字、跨片段拼接或引用 answer",
        "action": "立即停止；不得把 HG quote invalid 当 known diagnostic 放行",
    },
    {
        "code": "q29_not_skipped",
        "condition": "Q29 的 F 不是 skipped(no_scorable_claims)",
        "action": "立即停止；不得用 0.0 或其它 skipped 兜底",
    },
    {
        "code": "unexplained_drop",
        "condition": "有 baseline 的 case 出现 old - new > 0.10 + 1e-9 的未解释下降",
        "action": "停止并人工复核；恰好 0.10 不停止",
    },
    {
        "code": "second_typo_or_number_change",
        "condition": "第二次出现 evidence typo、数字/日期/金额改动",
        "action": "立即停止",
    },
    {
        "code": "unprocessed_items",
        "condition": "finalize 后 unprocessed_items > 0，或 10 条未全部终态",
        "action": "停止；不得把未处理 item 当 skipped",
    },
    {
        "code": "fingerprint_mismatch",
        "condition": (
            "prompt SHA / MANIFEST SHA / schema / metric / model / temperature / "
            "max_tokens / top_k 与申请不一致"
        ),
        "action": "拒绝运行或立即停止；不得静默换版本",
    },
    {
        "code": "activation_drift",
        "condition": "v1.2.0 被设为默认、active=true 或 runtime_active=true",
        "action": "立即停止；回到 frozen / active=false",
    },
]

FAILURE_HANDLING: dict[str, Any] = {
    "invalid": "不重试；保留 invalid_reason 与 validation_errors；停止并复审",
    "failed_execution": "同配置最多重试一次；不得改 Prompt/Schema/model/top_k",
    "skipped": "按 case 语义单独记录；不得把 skipped 当 PASS",
    "stop": "保留已完成结果与 run 快照；不启动 40；新 Run 需新批准",
    "no_prompt_tuning": "10 条期间不得改 Prompt、Schema、Service、目标或 stop conditions",
}

REPORT_REQUIREMENTS: list[str] = [
    "使用 docs/repair/phase3e/m1c-c4-report-template.md",
    (
        "逐条报告 status、F_coverage、F_strict（仅诊断）、C、R、"
        "invalid/skipped/failed、insufficient_count/ratio、known issue"
    ),
    "逐条写 PASS/FAIL/BLOCKED；Q29 只能按 skipped 语义判定",
    "HG 3 条（Q23/Q35/Q36）与 provisional 7 条分开，不混算均值",
    ("Q17 标 policy_relationship_target_reapproval；" "Q35/Q36 标 old run only，不冒充 v1.2.0 实测"),
    (
        "报告写 target v1.0.2 SHA、final_labels SHA、Prompt SHA、"
        "MANIFEST SHA、schema/metric version、dataset checksum"
    ),
    "报告写 adapter/model/temperature/max_tokens/top_k 与 run config_snapshot",
    "结论只能写 implemented/verified/blocked；不得自行写 accepted",
]

BOUNDARIES: list[str] = [
    "本文件是申请材料，不是 Judge 运行；未调用模型、未创建 Run",
    "不激活 v1.2.0；active 保持 false、runtime_active 保持 false",
    "不修改默认 RAG_JUDGE_PROMPT_VERSION=v1.0.0",
    "qwen-max / max_tokens / RAG_ADAPTER 只作本次 Run 的临时进程环境，不写入仓库或长期 .env，Run 后恢复",
    "不修改 Prompt、MANIFEST、Schema、Service、API、DB、migration 022",
    "不运行 40 条；10 条通过后才可单独申请 40 条",
    "不启动 M2/M3；不把 M1-C/M1-D 标 accepted",
    "不把 Q17/Q32 的预期标签写成实测；本申请不含 Q32",
]

APPROVAL_ITEMS: list[str] = [
    "确认 10 个 cases 与顺序：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36",
    "确认 v1.2.0 frozen Prompt SHA、MANIFEST SHA、schema v3、metric v3",
    "确认 run 配置：query / weknora / top_k=5 / qwen-max / temperature=0.0 / max_tokens=8192",
    "确认预算上限 CNY 0.80 与最大 48 次 Judge 调用",
    "确认停止条件与失败处理",
    "确认不会激活 v1.2.0、不会改默认版本、不会跑 40",
    "批准后才执行 10 条；执行后停下报告",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


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


def build_application() -> dict[str, Any]:
    target_data = load_json(TARGET_FILE)
    labels_data = load_json(LABELS_FILE)
    manifest = load_json(MANIFEST_FILE)
    targets = {case["case_id"]: case for case in target_data["cases"]}
    labels = {case["case_id"]: case for case in labels_data["labels"]}

    cases: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        target = targets[case_id]
        label = labels[case_id]
        target_values = target.get("targets") or {}
        expected_status = (
            "skipped(no_scorable_claims)" if target_values.get("F") == "skipped" else "evaluated"
        )
        cases.append(
            {
                "case_id": case_id,
                "group": label["group"],
                "final_category": label["final_category"],
                "context_count": int(label["context_availability"]),
                "baseline_status": label["baseline_status"],
                "baseline_reference": (
                    "old run only; not v1.2.0 measured"
                    if label["baseline_status"] == "available_old_run"
                    else "reused v1.1.5 baseline; reference only"
                ),
                "expected_status": expected_status,
                "targets": target_values,
                "target_source": target.get("target_source"),
                "target_status": target.get("target_status"),
                "variant_targets": target.get("variant_targets") or {},
                "variant_note": target.get("variant_note") or "",
                "known_issue": label.get("known_issue") or "",
                "known_non_pass": bool(target.get("known_non_pass")),
            }
        )

    return {
        "meta": {
            "name": "m1d1-ten-case-judge-application",
            "status": "pending_approval",
            "not_approved": True,
            "judge_run": False,
            "runtime_activated": False,
            "date": "2026-11-21",
            "design_commit": "071c3b6",
            "freeze_commit": FROZEN_COMMIT,
            "freeze_record": FREEZE_RECORD,
            "prompt_version": "v1.2.0",
            "prompt_status": manifest.get("status"),
            "prompt_active": manifest.get("active"),
            "manifest_sha256": sha256_bytes(MANIFEST_FILE.read_bytes()),
            "prompt_sha256": {
                name: sha256_text((PROMPT_DIR / name).read_text(encoding="utf-8"))
                for name in PROMPT_SHA
            },
            "schema_version": manifest.get("schema_version"),
            "rubric_version": manifest.get("rubric_version"),
            "metric_version": "v3",
            "target_file": TARGET_FILE.name,
            "target_sha256": sha256_bytes(TARGET_FILE.read_bytes()),
            "labels_file": LABELS_FILE.name,
            "labels_sha256": sha256_bytes(LABELS_FILE.read_bytes()),
            "report_template": REPORT_TEMPLATE,
        },
        "run_config": RUN_CONFIG,
        "case_summary": {
            "case_count": len(cases),
            "group_counts": {
                "human_gold": sum(1 for case in cases if case["group"] == "human_gold"),
                "provisional": sum(1 for case in cases if case["group"] == "provisional"),
            },
            "evaluated_expected": sum(
                1 for case in cases if case["expected_status"] == "evaluated"
            ),
            "skipped_expected": sum(1 for case in cases if case["expected_status"] != "evaluated"),
        },
        "cases": cases,
        "budget": BUDGET,
        "stop_conditions": STOP_CONDITIONS,
        "failure_handling": FAILURE_HANDLING,
        "report_requirements": REPORT_REQUIREMENTS,
        "boundaries": BOUNDARIES,
        "approval_items": APPROVAL_ITEMS,
        "judge_run": False,
        "runtime_activated": False,
    }


def build_validation(application: dict[str, Any], application_sha: str) -> dict[str, Any]:
    target_data = load_json(TARGET_FILE)
    labels_data = load_json(LABELS_FILE)
    targets = {case["case_id"]: case for case in target_data["cases"]}
    labels = {case["case_id"]: case for case in labels_data["labels"]}

    cases = application["cases"]
    case_ids = [case["case_id"] for case in cases]
    checks: list[dict[str, Any]] = [
        {"check": "application_status", "ok": application["meta"]["status"] == "pending_approval"},
        {"check": "not_approved", "ok": application["meta"]["not_approved"] is True},
        {"check": "judge_not_run", "ok": application["judge_run"] is False},
        {"check": "not_activated", "ok": application["runtime_activated"] is False},
        {"check": "case_count", "ok": len(cases) == 10},
        {"check": "case_ids", "ok": tuple(case_ids) == CASE_IDS},
        {
            "check": "case_ids_exist",
            "ok": all(case_id in targets and case_id in labels for case_id in CASE_IDS),
        },
        {
            "check": "group_counts",
            "ok": application["case_summary"]["group_counts"]
            == {"human_gold": 3, "provisional": 7},
        },
        {
            "check": "evaluated_expected",
            "ok": application["case_summary"]["evaluated_expected"] == 9,
        },
        {"check": "skipped_expected", "ok": application["case_summary"]["skipped_expected"] == 1},
        {
            "check": "q29_expected_skip",
            "ok": next(case for case in cases if case["case_id"] == "Q29")["expected_status"]
            == "skipped(no_scorable_claims)",
        },
        {
            "check": "q35_q36_old_run_only",
            "ok": all(
                next(case for case in cases if case["case_id"] == case_id)["baseline_status"]
                == "available_old_run"
                for case_id in ("Q35", "Q36")
            ),
        },
        {
            "check": "q36_variant_target",
            "ok": next(case for case in cases if case["case_id"] == "Q36")["variant_targets"]
            == {"C": [0.9, 1.0]},
        },
        {
            "check": "targets_match",
            "ok": all(
                case["targets"] == (targets[case["case_id"]].get("targets") or {}) for case in cases
            ),
        },
        {
            "check": "labels_match",
            "ok": all(
                case["group"] == labels[case["case_id"]]["group"]
                and case["final_category"] == labels[case["case_id"]]["final_category"]
                and case["context_count"] == int(labels[case["case_id"]]["context_availability"])
                and case["baseline_status"] == labels[case["case_id"]]["baseline_status"]
                for case in cases
            ),
        },
        {"check": "target_sha256", "ok": application["meta"]["target_sha256"] == TARGET_SHA},
        {"check": "labels_sha256", "ok": application["meta"]["labels_sha256"] == LABELS_SHA},
        {"check": "manifest_sha256", "ok": application["meta"]["manifest_sha256"] == MANIFEST_SHA},
        {
            "check": "prompt_sha256",
            "ok": application["meta"]["prompt_sha256"] == PROMPT_SHA,
        },
        {"check": "manifest_frozen", "ok": application["meta"]["prompt_status"] == "frozen"},
        {"check": "manifest_inactive", "ok": application["meta"]["prompt_active"] is False},
        {
            "check": "schema_v3",
            "ok": application["meta"]["schema_version"] == "rag_judge_schema_v3",
        },
        {"check": "metric_v3", "ok": application["meta"]["metric_version"] == "v3"},
        {
            "check": "default_v100",
            "ok": application["run_config"]["default_prompt_version"] == "v1.0.0",
        },
        {"check": "query_mode", "ok": application["run_config"]["execution_mode"] == "query"},
        {"check": "adapter_weknora", "ok": application["run_config"]["adapter"] == "weknora"},
        {"check": "top_k", "ok": application["run_config"]["top_k"] == 5},
        {"check": "model", "ok": application["run_config"]["model"] == "qwen-max"},
        {"check": "temperature", "ok": application["run_config"]["temperature"] == 0.0},
        {"check": "max_tokens", "ok": application["run_config"]["max_tokens"] == 8192},
        {
            "check": "env_scope",
            "ok": "process-local" in application["run_config"]["env_scope"],
        },
        {
            "check": "judge_metrics",
            "ok": application["run_config"]["judge_metrics"]
            == ["faithfulness", "answer_correctness", "answer_relevancy"],
        },
        {
            "check": "strict_not_judge_metric",
            "ok": "faithfulness_strict" not in application["run_config"]["judge_metrics"],
        },
        {
            "check": "strict_derived",
            "ok": application["run_config"]["derived_metrics"] == ["faithfulness_strict"],
        },
        {
            "check": "budget_calls",
            "ok": application["budget"]["primary_judge_calls"] == 30
            and application["budget"]["max_judge_calls"] == 48,
        },
        {
            "check": "budget_ceiling",
            "ok": application["budget"]["estimated_cost_cny"]["ceiling"] == 0.80,
        },
        {
            "check": "stop_conditions",
            "ok": {item["code"] for item in application["stop_conditions"]}
            >= {
                "preflight_failure",
                "invalid_contract",
                "failed_execution",
                "hg_supported_quote_invalid",
                "q29_not_skipped",
                "unexplained_drop",
            },
        },
        {
            "check": "boundaries",
            "ok": any("不激活" in item for item in application["boundaries"])
            and any("40" in item for item in application["boundaries"]),
        },
        {
            "check": "application_sha256",
            "ok": application_sha
            == sha256_bytes(
                (json.dumps(application, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
            ),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "name": "m1d1-ten-case-application-validation",
        "kind": "static_application_validation_not_judge_run",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "application_sha256": application_sha,
        "judge_run": False,
        "runtime_activated": False,
    }


def build_markdown(application: dict[str, Any], application_sha: str, validation_sha: str) -> str:
    meta = application["meta"]
    config = application["run_config"]
    budget = application["budget"]
    input_low, input_high = budget["estimated_input_tokens"]
    output_low, output_high = budget["estimated_output_tokens"]
    lines = [
        "# M1-D-1 10 条 Judge 申请材料",
        "",
        "> 状态：`pending_approval`。**仅申请材料，未运行 Judge、未创建 Run、未激活 v1.2.0。**",
        f"> 日期：2026-11-21；frozen 提交：`{meta['freeze_commit']}`；"
        f"freeze record：`{meta['freeze_record']}`",
        f"> Prompt：`{meta['prompt_version']}` / `{meta['prompt_status']}` / "
        f"schema `{meta['schema_version']}` / metric `{meta['metric_version']}`",
        f"> MANIFEST SHA256：`{meta['manifest_sha256']}`",
        f"> 申请 JSON SHA256：`{application_sha}`",
        f"> validation SHA256：`{validation_sha}`",
        "",
        "## 1. 申请结论",
        "",
        "本文件只申请 **10 条** Judge：Q01/Q04/Q11/Q17/Q21/Q23/Q29/Q31/Q35/Q36。",
        "10 条通过后才允许单独申请 40 条；本申请不包含 40 条、不激活 v1.2.0、不改默认版本。",
        "",
        "## 2. 冻结资产",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| Prompt 版本 | `{meta['prompt_version']}` |",
        f"| Prompt 状态 | `{meta['prompt_status']}`；`active=false` |",
        f"| MANIFEST SHA256 | `{meta['manifest_sha256']}` |",
        f"| `faithfulness.txt` | `{meta['prompt_sha256']['faithfulness.txt']}` |",
        f"| `answer_correctness.txt` | `{meta['prompt_sha256']['answer_correctness.txt']}` |",
        f"| `answer_relevancy.txt` | `{meta['prompt_sha256']['answer_relevancy.txt']}` |",
        f"| Schema / Metric | `{meta['schema_version']}` / `{meta['metric_version']}` |",
        f"| target | `{meta['target_file']}`（`{meta['target_sha256']}`） |",
        f"| final labels | `{meta['labels_file']}`（`{meta['labels_sha256']}`） |",
        "| 默认版本 | `v1.0.0`（保持不变） |",
        "",
        "## 3. 10 个 Cases",
        "",
        "| Case | group | category | context | baseline | expected status | "
        "F target | C target | R target | known issue |",
        "|---|---|---|---:|---|---|---|---|---|---|",
    ]
    for case in application["cases"]:
        targets = case["targets"]
        lines.append(
            f"| {case['case_id']} | {case['group']} | {case['final_category']} | "
            f"{case['context_count']} | {case['baseline_status']} | {case['expected_status']} | "
            f"{target_display(targets.get('F'))} | {target_display(targets.get('C'))} | "
            f"{target_display(targets.get('R'))} | {case['known_issue'] or '—'} |"
        )
    lines.extend(
        [
            "",
            "固定口径：",
            "",
            "- Q29 的 F 必须是 `skipped(no_scorable_claims)`；不得 0.0、不得用 skipped 兜底其它案例；",
            "- Q35/Q36 只用 old run 参考，不把旧结果冒充 v1.2.0 实测；",
            "- Q17 使用 v1.0.2 的 `0.7–0.9` 目标；旧 `0.9–1.0` 已被 reapproval 取代；",
            "- Q21 只有 F 目标；Q21#3 保持 `insufficient_evidence`；",
            ("- Q36 base C 目标 `0.5–0.6`；若回答披露文档冲突，" "按 variant `0.9–1.0` 判定，报告必须写明用了哪一口径；"),
            "- Q23/Q35/Q36 为 Human Gold；其余 7 条为 provisional，报告不得混算均值。",
            "",
            "## 4. Run 配置",
            "",
            "| 项 | 值 |",
            "|---|---|",
            f"| execution_mode | `{config['execution_mode']}` |",
            f"| adapter | `{config['adapter']}` |",
            f"| dataset | {config['dataset']} |",
            f"| split / limit | `{config['split']}` / `{config['limit']}` |",
            f"| top_k | `{config['top_k']}` |",
            f"| judge_metrics | `{', '.join(config['judge_metrics'])}` |",
            f"| derived_metrics | `{', '.join(config['derived_metrics'])}` |",
            f"| judge_prompt_version | `{config['judge_prompt_version']}`（显式指定，不改默认） |",
            f"| model | `{config['model']}` |",
            f"| temperature | `{config['temperature']}` |",
            f"| max_tokens | `{config['max_tokens']}` |",
            f"| soft budget | `{config['soft_budget_seconds']}s` |",
            f"| schema / metric | `{config['schema_version']}` / `{config['metric_version']}` |",
            "",
            "关键环境变量（不包含密钥）：",
            "",
            "```text",
            *[f"{key}={value}" for key, value in config["env"].items()],
            "```",
            "",
            f"- WeKnora KB：`{config['weknora']['knowledge_base_id']}`；"
            "agent/tenant 使用现有部署值，并在 Run 快照中记录；",
            f"- Judge endpoint：{config['llm_endpoint']}；",
            f"- 环境作用域：{config['env_scope']}；",
            "- 选择 10 条：按 `item_key` 解析 `item_ids`；Run 快照必须记录实际 UUID 与 dataset checksum。",
            "",
            "## 5. 方法与解释边界",
            "",
            "- 本次是平台 `query` Run 的端到端闸门：答案/contexts 由 WeKnora 重新生成；",
            "- 10 条目标是 Judge 质量目标；Q35/Q36 的旧 run 只作参考，不作为固定输入复现；",
            "- 若要求“固定同一批 answer/contexts，只切换 Judge Prompt”的 Judge-only 对比，本申请不适用，需另立方案；",
            "- 报告不得把 v1.1.5 旧值写成 v1.2.0 实测，也不得把 Q17/Q32 的预期标签写成实测。",
            "",
            "## 6. 预算与调用量",
            "",
            "| 项 | 值 |",
            "|---|---:|",
            f"| 主运行 case 数 | {budget['primary_case_runs']} |",
            f"| 主运行 Judge 调用 | {budget['primary_judge_calls']}（10 × 3 指标） |",
            f"| 条件重复 cases | {'/'.join(budget['conditional_repeat_cases'])} |",
            f"| 条件重复额外 case-run | {budget['conditional_repeat_extra_case_runs']} |",
            f"| 最大 case-run | {budget['max_case_runs']} |",
            f"| 最大 Judge 调用 | {budget['max_judge_calls']} |",
            f"| 估算 input tokens | {input_low:,}–{input_high:,} |",
            f"| 估算 output tokens | {output_low:,}–{output_high:,} |",
            f"| 预计成本 | CNY {budget['estimated_cost_cny']['expected']:.2f} |",
            f"| 上限 | CNY {budget['estimated_cost_cny']['upper']:.2f} |",
            f"| **批准 ceiling** | **CNY {budget['estimated_cost_cny']['ceiling']:.2f}** |",
            "",
            f"计价口径：{budget['price_basis']}。{budget['note']}。",
            "",
            "## 7. 停止条件与失败处理",
            "",
            "| code | 条件 | 动作 |",
            "|---|---|---|",
        ]
    )
    for item in application["stop_conditions"]:
        lines.append(f"| `{item['code']}` | {item['condition']} | {item['action']} |")
    lines.extend(
        [
            "",
            "失败处理：",
            "",
            *[f"- **{key}**：{value}" for key, value in application["failure_handling"].items()],
            "",
            "## 8. 报告要求",
            "",
            *[f"- {item}" for item in application["report_requirements"]],
            "",
            "## 9. 边界",
            "",
            *[f"- {item}" for item in application["boundaries"]],
            "",
            "## 10. 批准清单",
            "",
            *[f"- [ ] {item}" for item in application["approval_items"]],
            "",
            "批准后只执行 10 条；执行完停下报告。10 条通过后才单独申请 40 条。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    application = build_application()
    application_bytes = (json.dumps(application, ensure_ascii=False, indent=1) + "\n").encode(
        "utf-8"
    )
    OUT_JSON.write_bytes(application_bytes)
    application_sha = sha256_bytes(application_bytes)

    validation = build_validation(application, application_sha)
    validation_bytes = (json.dumps(validation, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    OUT_VALIDATION.write_bytes(validation_bytes)
    validation_sha = sha256_bytes(validation_bytes)

    OUT_SHA.write_text(
        f"{application_sha}  {OUT_JSON.name}\n{validation_sha}  {OUT_VALIDATION.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    OUT_MD.write_text(
        build_markdown(application, application_sha, validation_sha),
        encoding="utf-8",
        newline="\n",
    )

    print(
        json.dumps(
            {
                "status": validation["status"],
                "checks": len(validation["checks"]),
                "failed": sum(1 for item in validation["checks"] if not item["ok"]),
                "application_sha256": application_sha,
                "validation_sha256": validation_sha,
                "cases": application["case_summary"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    failed = [item for item in validation["checks"] if not item["ok"]]
    if failed:
        raise SystemExit(f"validation failed: {failed}")


if __name__ == "__main__":
    main()
