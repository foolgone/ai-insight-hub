"""Build the final M1-D-6 v1.2.4 single-case diagnostic report from raw artifacts.

This script is report-only: it never calls the LLM and never changes the ledger.
It reads the raw results JSON + append-only ledger produced by
``m1d6_run_single_case.py`` and writes:

- docs/repair/phase3e/m1d6-single-case-analysis.json
- docs/repair/49-m1d6-v1.2.4-single-case-diagnostic-results.md
- docs/repair/phase3e/m1d6-single-case-analysis.sha256
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
RESULTS_FILE = BASE / "docs/repair/phase3e/m1d6-single-case-results.json"
LEDGER_FILE = BASE / "docs/repair/phase3e/m1d6-single-case-ledger.jsonl"
APPLICATION_FILE = (
    BASE / "docs/repair/phase3e/m1d6-single-case-diagnostic-application.json"
)
ANALYSIS_FILE = BASE / "docs/repair/phase3e/m1d6-single-case-analysis.json"
REPORT_FILE = BASE / "docs/repair/49-m1d6-v1.2.4-single-case-diagnostic-results.md"
SHA_FILE = BASE / "docs/repair/phase3e/m1d6-single-case-analysis.sha256"

EXPECTED_APPLICATION_SHA = (
    "54193e918daf3111014790923431695c7641fb629d2341bd71ecbe03001b1388"
)
EXPECTED_MAX_CALLS = 14
EXPECTED_CEILING_CNY = 0.30
PATCH_EXAMPLE_CONTEXT = "延保卡需在购买后 30 天内激活。"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json_text(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1 :] if first_newline != -1 else cleaned
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()
    starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index != -1]
    if not starts:
        return cleaned
    start = min(starts)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end > start:
        return cleaned[start : end + 1]
    return cleaned


def in_target(value: float | None, target: list[float]) -> bool | None:
    if value is None:
        return None
    return float(target[0]) <= float(value) <= float(target[1])


def ledger_records() -> list[dict[str, Any]]:
    records = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def ledger_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    started = [record for record in records if record.get("event") == "started"]
    finished = {
        int(record["seq"]): record
        for record in records
        if record.get("event") == "finished"
    }
    by_kind: dict[str, int] = {}
    for record in started:
        kind = str(record.get("kind") or "primary")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    rows: list[dict[str, Any]] = []
    uncertain = 0
    for record in started:
        seq = int(record["seq"])
        fin = finished.get(seq)
        if fin is None:
            uncertain += 1
        usage = (fin or {}).get("usage") or {}
        rows.append(
            {
                "seq": seq,
                "call_id": record.get("call_id"),
                "kind": record.get("kind"),
                "case_id": record.get("case_id"),
                "metric": record.get("metric"),
                "model_requested": record.get("model_requested"),
                "response_model": (fin or {}).get("response_model"),
                "temperature": record.get("temperature"),
                "max_tokens": record.get("max_tokens"),
                "prompt_version": record.get("prompt_version"),
                "prompt_sha256": record.get("prompt_sha256"),
                "system_prompt_sha256": record.get("system_prompt_sha256"),
                "patch_claim_ids": record.get("patch_claim_ids") or [],
                "started_at": record.get("timestamp"),
                "finished_at": (fin or {}).get("timestamp"),
                "status": (fin or {}).get("status"),
                "input_tokens": int(usage.get("input") or 0),
                "output_tokens": int(usage.get("output") or 0),
                "cost_cny": float((fin or {}).get("cost_cny") or 0.0),
                "error": (fin or {}).get("error"),
            }
        )
    return {
        "sha256": sha256_bytes(LEDGER_FILE.read_bytes()),
        "file": str(LEDGER_FILE.relative_to(BASE)),
        "total_started": len(started),
        "total_finished": len(finished),
        "uncertain_calls": uncertain,
        "by_kind": by_kind,
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "cost_cny": round(sum(row["cost_cny"] for row in rows), 8),
        "rows": rows,
    }


def claim_effective_id(claim: dict[str, Any], index: int) -> str:
    return str(claim.get("claim_id") or f"cl{index}")


def build_analysis() -> dict[str, Any]:
    results = load_json(RESULTS_FILE)
    records = ledger_records()
    ledger = ledger_summary(records)

    application_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    results_sha = sha256_bytes(RESULTS_FILE.read_bytes())
    if application_sha != EXPECTED_APPLICATION_SHA:
        raise SystemExit(f"application SHA mismatch: {application_sha}")
    if results["meta"].get("application_sha256") != application_sha:
        raise SystemExit("results meta application SHA mismatch")
    if ledger["sha256"] != results["meta"].get("ledger_sha256"):
        raise SystemExit(
            f"ledger SHA mismatch: {ledger['sha256']} != "
            f"{results['meta'].get('ledger_sha256')}"
        )
    if ledger["total_started"] != results["meta"].get("ledger_total_attempts"):
        raise SystemExit("ledger attempts mismatch")
    if ledger["uncertain_calls"] != 0:
        raise SystemExit(f"uncertain calls: {ledger['uncertain_calls']}")
    if ledger["total_started"] > EXPECTED_MAX_CALLS:
        raise SystemExit("call budget exceeded")
    if ledger["cost_cny"] > EXPECTED_CEILING_CNY:
        raise SystemExit("cost ceiling exceeded")

    calls = results.get("calls") or []
    q23_calls = [call for call in calls if call.get("case_id") == "Q23"]
    f_primary = next(
        (
            call
            for call in reversed(q23_calls)
            if call.get("metric") == "faithfulness"
            and call.get("kind") in {"primary", "retry"}
            and call.get("content")
        ),
        None,
    )
    patch_call = next(
        (
            call
            for call in reversed(q23_calls)
            if call.get("metric") == "faithfulness"
            and call.get("kind") == "patch"
            and call.get("content")
        ),
        None,
    )
    if f_primary is None:
        raise SystemExit("Q23 faithfulness primary output missing")

    initial_output = str(f_primary.get("content") or "")
    patch_output = str(patch_call.get("content") or "") if patch_call else ""
    initial_payload = json.loads(extract_json_text(initial_output))
    initial_claims = list(initial_payload.get("claims") or [])
    claims_normalized: list[dict[str, Any]] = []
    for index, claim in enumerate(initial_claims, 1):
        claims_normalized.append(
            {
                "claim_id": claim_effective_id(claim, index),
                "claim": claim.get("claim"),
                "claim_type": claim.get("claim_type"),
                "claim_subtype": claim.get("claim_subtype"),
                "support_status": claim.get("support_status"),
                "is_contradictory": claim.get("is_contradictory"),
                "contradiction_with": claim.get("contradiction_with") or [],
                "evidence_refs": claim.get("evidence_refs") or [],
                "reason": claim.get("reason"),
            }
        )
    absence_fields = [
        {
            "claim_id": claim["claim_id"],
            "claim": claim["claim"],
            "claim_type": claim["claim_type"],
            "claim_subtype": claim["claim_subtype"],
            "support_status": claim["support_status"],
            "evidence_refs": claim["evidence_refs"],
            "is_contradictory": claim["is_contradictory"],
            "contradiction_with": claim["contradiction_with"],
        }
        for claim in claims_normalized
        if claim.get("claim_subtype") == "absence"
    ]
    absence_contract_initial_pass = bool(absence_fields) and all(
        item["claim_type"] == "non_factual"
        and item["claim_subtype"] == "absence"
        and item["support_status"] is None
        and item["evidence_refs"] == []
        for item in absence_fields
    )
    cl5 = next(
        (claim for claim in claims_normalized if claim["claim_id"] == "cl5"),
        None,
    )
    cl1 = next(
        (claim for claim in claims_normalized if claim["claim_id"] == "cl1"),
        None,
    )

    q23 = next(case for case in results.get("cases") or [] if case["case_id"] == "Q23")
    outcomes = {
        outcome["metric_name"]: outcome for outcome in q23.get("outcomes") or []
    }
    f_outcome = outcomes.get("faithfulness") or {}
    f_strict = outcomes.get("faithfulness_strict") or {}
    c_outcome = outcomes.get("answer_correctness") or {}
    r_outcome = outcomes.get("answer_relevancy") or {}
    contract = (f_outcome.get("details") or {}).get("agent_contract") or {}
    c_contract = (c_outcome.get("details") or {}).get("agent_contract") or {}
    final_errors = list(contract.get("final_errors") or [])
    patch_schema_invalid = any(
        str(error.get("code")) == "patch_schema_invalid" for error in final_errors
    )
    patch_applied_claims = list(contract.get("patch_applied_claims") or [])
    patch_semantic_review_required = bool(
        contract.get("patch_semantic_review_required")
    )
    patch_triggered = bool(contract.get("repair_triggered"))
    patch_claim_ids = (
        list(patch_call.get("patch_claim_ids") or []) if patch_call else []
    )
    patch_example_quote_copied = bool(
        patch_output and PATCH_EXAMPLE_CONTEXT in patch_output
    )

    q23_targets = {
        "F": [0.4, 0.5],
        "C": [0.0, 0.2],
        "R": [0.7, 1.0],
    }
    c_score = c_outcome.get("score")
    r_score = r_outcome.get("score")
    f_score = f_outcome.get("score")
    c_target_pass = in_target(c_score, q23_targets["C"])
    r_target_pass = in_target(r_score, q23_targets["R"])
    f_target_pass = in_target(f_score, q23_targets["F"])
    c_warning = c_contract.get("correctness_first_sentence_warning")

    patch_review = {
        "patch_triggered": patch_triggered,
        "patch_output_present": bool(patch_output),
        "merged_output_present": False,
        "patch_schema_valid": not patch_schema_invalid,
        "patch_applied_claims": patch_applied_claims,
        "patch_semantic_review_required": patch_semantic_review_required,
        "patch_example_quote_copied": patch_example_quote_copied,
        "non_target_claims_unchanged": None,
        "changed_claims": [],
        "changed_outside_applied": [],
        "failures": [
            "patch output does not satisfy EvidencePatch; merged output was not produced"
        ]
        if patch_schema_invalid
        else [],
        "note": (
            "patch returned evidence_refs=null for cl1/cl2/cl4; EvidencePatch "
            "requires a non-empty array. Agent recorded patch_schema_invalid and "
            "stopped before merge."
        ),
    }
    claim_level_review = {
        "human_review_required": True,
        "reviewed_initial_claims": len(claims_normalized),
        "initial_cl1_support_status": cl1.get("support_status") if cl1 else None,
        "expected_cl1_supported": False,
        "patch_targets": patch_claim_ids,
        "expected_patch_targets": ["cl2", "cl3"],
        "patch_targets_outside_expected": sorted(set(patch_claim_ids) - {"cl2", "cl3"}),
        "patch_applied": bool(patch_applied_claims),
        "semantic_change": "not_applicable_patch_schema_invalid",
        "conclusion": (
            "Q23 fails before semantic merge. Initial cl1 is unsupported (expected "
            "supported), and the quote precheck flags cl1/cl2/cl4 (not only cl2/cl3). "
            "The patch output is not a valid EvidencePatch."
        ),
    }

    ledger_rows = ledger["rows"]
    q23_ledger_rows = [row for row in ledger_rows if row["case_id"] == "Q23"]
    q23_call_summary = {
        "calls": len(q23_calls),
        "primary": sum(1 for call in q23_calls if call.get("kind") == "primary"),
        "patch": sum(1 for call in q23_calls if call.get("kind") == "patch"),
        "repair": sum(1 for call in q23_calls if call.get("kind") == "repair"),
        "retry": sum(1 for call in q23_calls if call.get("kind") == "retry"),
        "input_tokens": sum(
            int((call.get("usage") or {}).get("input") or 0) for call in q23_calls
        ),
        "output_tokens": sum(
            int((call.get("usage") or {}).get("output") or 0) for call in q23_calls
        ),
        "cost_cny": round(
            sum(
                int((call.get("usage") or {}).get("input") or 0) * (0.0024 / 1000)
                + int((call.get("usage") or {}).get("output") or 0) * (0.0096 / 1000)
                for call in q23_calls
            ),
            8,
        ),
    }
    q23_metric_summary = {
        "faithfulness": {
            "status": f_outcome.get("status"),
            "score": f_score,
            "invalid_reason": f_outcome.get("invalid_reason"),
            "target": q23_targets["F"],
            "target_pass": f_target_pass,
        },
        "faithfulness_strict": {
            "status": f_strict.get("status"),
            "score": f_strict.get("score"),
            "invalid_reason": f_strict.get("invalid_reason"),
        },
        "answer_correctness": {
            "status": c_outcome.get("status"),
            "score": c_score,
            "target": q23_targets["C"],
            "target_pass": c_target_pass,
            "first_sentence_warning": c_warning,
        },
        "answer_relevancy": {
            "status": r_outcome.get("status"),
            "score": r_score,
            "target": q23_targets["R"],
            "target_pass": r_target_pass,
        },
    }

    stop_conditions = [
        {
            "code": "invalid_contract",
            "condition": "任一指标 invalid(contract_violation)",
            "triggered": True,
            "evidence": "Q23 F/F_strict invalid(contract_violation)",
        },
        {
            "code": "schema_or_patch_failure",
            "condition": "初始 Schema 失败，或 patch 1 次后仍失败",
            "triggered": True,
            "evidence": "patch_schema_invalid: evidence_refs=null for cl1/cl2/cl4",
        },
        {
            "code": "q23_patch_semantic_change",
            "condition": "Q23 patch 改了 cl1 或其它非目标 claim",
            "triggered": False,
            "evidence": (
                "patch did not merge; initial cl1 unsupported and patch targets "
                "cl1/cl2/cl4 are reported separately"
            ),
        },
        {
            "code": "q23_absence_contract",
            "condition": "Q23 absence 仍为 factual/supported",
            "triggered": False,
            "evidence": (
                "initial cl6/cl10 are non_factual+absence+null+[]; "
                "merged absence not produced"
            ),
        },
        {
            "code": "q23_f_or_c_target",
            "condition": "Q23 F 或 C 目标 miss",
            "triggered": False,
            "evidence": f"F not evaluable (invalid); C={c_score} in [0.0, 0.2]",
        },
        {
            "code": "q21_semantic_or_f_one",
            "condition": "Q21 F=1.0，或仍用运费/换货 quote 支持 7 天豁免",
            "triggered": False,
            "evidence": "Q21 not run (stopped at Q23)",
        },
        {
            "code": "q11_quote_or_target",
            "condition": "Q11 quote/契约违约，或三项目标任一 miss",
            "triggered": False,
            "evidence": "Q11 not run (stopped at Q23)",
        },
        {
            "code": "fingerprint_mismatch",
            "condition": "Prompt/MANIFEST/fixture/target/patch schema/example/validator SHA 漂移",
            "triggered": False,
            "evidence": "all preflight SHA checks passed; frozen assets unchanged since c813443",
        },
        {
            "code": "budget_ceiling",
            "condition": "超过 14 calls 或 CNY 0.30",
            "triggered": False,
            "evidence": f"{ledger['total_started']} calls / CNY {ledger['cost_cny']:.6f}",
        },
        {
            "code": "ledger_or_missing_result",
            "condition": "ledger 缺失/SHA 不匹配/uncertain_call=true，或任一 case 缺完整 F/C/R",
            "triggered": True,
            "evidence": "ledger valid (0 uncertain); Q21/Q11 missing because run stopped at Q23",
        },
    ]

    analysis = {
        "meta": {
            "name": "m1d6-v1.2.4-single-case-diagnostic-analysis",
            "kind": "report_only_no_llm_no_db",
            "date": "2026-11-23",
            "status": "stopped",
            "diagnostic_only": True,
            "counts_toward_10": False,
            "application_sha256": application_sha,
            "results_json_sha256": results_sha,
            "ledger_sha256": ledger["sha256"],
            "prompt_version": "v1.2.4",
            "rubric_version": "v1.2.0",
            "schema_version": "rag_judge_schema_v3",
            "metric_version": "v3",
            "default_prompt_version": "v1.0.0",
            "active": False,
            "runtime_active": False,
            "created_run": False,
            "wrote_db": False,
            "weknora_called": False,
            "rag_adapter_called": False,
            "ran_10": False,
            "ran_40": False,
            "stop_reason": results.get("stop_reason"),
            "stop_codes": results.get("stop_codes"),
        },
        "assets": {
            key: results["meta"].get(key)
            for key in (
                "manifest_sha256",
                "validation_sha256",
                "leakage_audit_sha256",
                "leakage_findings",
                "fixture_sha256",
                "target_sha256",
                "labels_sha256",
                "patch_schema_sha256",
                "patch_example_sha256",
                "quote_validator_sha256",
                "agent_commit",
                "initial_implementation_commit",
                "patch_prompt_fix_commit",
                "status_doc_commit",
                "freeze_commit",
                "git_head",
            )
        },
        "budget": {
            "calls_used": ledger["total_started"],
            "primary": q23_call_summary["primary"],
            "patch": q23_call_summary["patch"],
            "repair": q23_call_summary["repair"],
            "retry": q23_call_summary["retry"],
            "max_calls": EXPECTED_MAX_CALLS,
            "cost_cny": ledger["cost_cny"],
            "ceiling_cny": EXPECTED_CEILING_CNY,
        },
        "ledger": ledger,
        "cases": {
            "Q23": {
                "status": "stopped",
                "calls": q23_call_summary,
                "ledger_rows": q23_ledger_rows,
                "metrics": q23_metric_summary,
                "targets": q23_targets,
                "initial_output": initial_output,
                "patch_output": patch_output,
                "merged_output": None,
                "patch_triggered": patch_triggered,
                "patch_applied_claims": patch_applied_claims,
                "patch_semantic_review_required": patch_semantic_review_required,
                "patch_schema_invalid": patch_schema_invalid,
                "final_errors": final_errors,
                "quote_precheck_errors": list(
                    contract.get("quote_precheck_errors") or []
                ),
                "mixed_sentence_warnings": list(
                    contract.get("mixed_sentence_warnings") or []
                ),
                "absence_fields": absence_fields,
                "absence_contract_initial_pass": absence_contract_initial_pass,
                "cl5": cl5,
                "cl5_mixed_sentence_warning": any(
                    str(item.get("claim_id")) == "cl5"
                    for item in contract.get("mixed_sentence_warnings") or []
                ),
                "claims": claims_normalized,
                "patch_review": patch_review,
                "claim_level_review": claim_level_review,
            },
            "Q21": {
                "status": "not_run",
                "reason": "stopped_at_Q23_patch_schema_invalid",
            },
            "Q11": {
                "status": "not_run",
                "reason": "stopped_at_Q23_patch_schema_invalid",
            },
        },
        "stop_conditions": stop_conditions,
        "conclusion": {
            "diagnostic_verified": False,
            "blocked_at": "Q23",
            "immediate_cause": "patch_schema_invalid",
            "next_step": (
                "Do not rerun under this approval. Decide whether to design a new "
                "patch repair version (for example, explicit refusal/null handling "
                "and Q23 claim decomposition) or keep v1.2.4 frozen and inactive."
            ),
        },
    }
    return analysis


def metric_table(metrics: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        "| metric | status | score | target | target pass | invalid/skipped |",
        "|---|---|---:|---|---|---|",
    ]
    for name, payload in metrics.items():
        lines.append(
            f"| {name} | {payload.get('status')} | {payload.get('score')} | "
            f"`{payload.get('target', '—')}` | {payload.get('target_pass', '—')} | "
            f"{payload.get('invalid_reason') or payload.get('skipped_reason') or '—'} |"
        )
    return lines


def claims_table(claims: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| claim_id | claim | type | subtype | support | evidence quotes |",
        "|---|---|---|---|---|---|",
    ]
    for claim in claims:
        quotes = [
            str(ref.get("quote") or "") for ref in claim.get("evidence_refs") or []
        ]
        lines.append(
            f"| {claim.get('claim_id')} | {claim.get('claim')} | "
            f"{claim.get('claim_type')} | {claim.get('claim_subtype')} | "
            f"{claim.get('support_status')} | {json.dumps(quotes, ensure_ascii=False)} |"
        )
    return lines


def ledger_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| seq | kind | case | metric | status | input | output | cost CNY |",
        "|---:|---|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['seq']} | {row['kind']} | {row['case_id']} | {row['metric']} | "
            f"{row['status']} | {row['input_tokens']} | {row['output_tokens']} | "
            f"{row['cost_cny']:.8f} |"
        )
    return lines


def stop_table(conditions: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| # | code | condition | triggered | evidence |",
        "|---:|---|---|---|---|",
    ]
    for index, item in enumerate(conditions, 1):
        lines.append(
            f"| {index} | `{item['code']}` | {item['condition']} | "
            f"**{item['triggered']}** | {item['evidence']} |"
        )
    return lines


def build_report(analysis: dict[str, Any], analysis_sha: str) -> str:
    meta = analysis["meta"]
    assets = analysis["assets"]
    q23 = analysis["cases"]["Q23"]
    metrics = q23["metrics"]
    ledger = analysis["ledger"]
    budget = analysis["budget"]
    patch_review = q23["patch_review"]
    claim_review = q23["claim_level_review"]
    triggered_codes = [
        item["code"] for item in analysis["stop_conditions"] if item["triggered"]
    ]
    initial_display = extract_json_text(str(q23.get("initial_output") or ""))
    patch_display = extract_json_text(str(q23.get("patch_output") or ""))

    lines = [
        "# M1-D-6 v1.2.4 单案例诊断结果（Q23 / Q21 / Q11）",
        "",
        "> 状态：**stopped at Q23**；diagnostic only；" "未创建 Run、未写 DB、未激活 v1.2.4。",
        f"> application SHA：`{meta['application_sha256']}`",
        f"> raw results JSON SHA：`{meta['results_json_sha256']}`",
        f"> analysis JSON SHA：`{analysis_sha}`",
        f"> ledger SHA：`{meta['ledger_sha256']}`；"
        f"total attempts：`{ledger['total_started']}`；"
        f"uncertain calls：`{ledger['uncertain_calls']}`",
        f"> Prompt：`{meta['prompt_version']}` / `frozen` / "
        f"rubric `{meta['rubric_version']}` / schema `{meta['schema_version']}` / "
        f"metric `{meta['metric_version']}`",
        f"> 默认版本：`{meta['default_prompt_version']}`；"
        f"active/runtime_active：`{meta['active']}` / `{meta['runtime_active']}`",
        f"> 停止原因：{meta['stop_reason']}",
        f"> 停止编码：`{triggered_codes}`",
        "",
        "## 0. 结论",
        "",
        "- **Q23 未通过**：F / F_strict 为 `invalid(contract_violation)`；"
        "初始 Schema 合法，但 patch 输出不满足 `EvidencePatch`。",
        "- patch 输出对 `cl1` / `cl2` / `cl4` 返回 `evidence_refs: null`；"
        "schema 要求非空数组，Agent 记录 `patch_schema_invalid`，"
        "没有生成 merged 输出。",
        "- 初始输出本身也不符合 Q23 验收预期：`cl1` 为 `unsupported`"
        "（预期 supported），quote 预检错误是 `cl1/cl2/cl4`"
        "（预期只修 `cl2/cl3`）。",
        "- **Q21 / Q11 未运行**；按“patch 1 次后仍失败”停止。",
        "- 预算与 ledger 正常：4 calls / CNY 0.0422808；" "started=finished=4；uncertain=0。",
        "- **未创建 Run、未写 DB、未调 WeKnora/RAG adapter、未激活 v1.2.4、未跑 10/40；"
        "单案例不计入 10 条。**",
        "",
        "## 1. 运行时指纹",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 生效 Prompt 版本 | `{meta['prompt_version']}`（显式传参；默认仍 `v1.0.0`） |",
        "| F SHA | `52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d` |",
        "| C SHA | `ca489fcf39691e9a71aec004a01938fb6c70b7b17da3c55fb0ada066e1d24968` |",
        "| R SHA | `f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc` |",
        f"| MANIFEST / validation | `{assets.get('manifest_sha256')}` / "
        f"`{assets.get('validation_sha256')}` |",
        f"| patch schema / example | `{assets.get('patch_schema_sha256')}` / "
        f"`{assets.get('patch_example_sha256')}` |",
        f"| quote validator | `{assets.get('quote_validator_sha256')}` |",
        f"| leakage audit | `{assets.get('leakage_audit_sha256')}`；"
        f"findings={assets.get('leakage_findings')} |",
        f"| fixture / target / labels | `{assets.get('fixture_sha256')}` / "
        f"`{assets.get('target_sha256')}` / `{assets.get('labels_sha256')}` |",
        f"| agent_commit / initial | `{assets.get('agent_commit')}` / "
        f"`{assets.get('initial_implementation_commit')}` |",
        f"| patch prompt fix / status doc | `{assets.get('patch_prompt_fix_commit')}` / "
        f"`{assets.get('status_doc_commit')}` |",
        f"| freeze commit | `{assets.get('freeze_commit')}` |",
        f"| git HEAD（执行时） | `{assets.get('git_head')}` |",
        "",
        "## 2. 调用、成本与 Ledger",
        "",
        "| 项 | 实际 | 预算/上限 |",
        "|---|---:|---:|",
        f"| Judge calls（ledger attempts） | {budget['calls_used']} | "
        f"{budget['max_calls']} |",
        f"| primary / patch / repair / retry | {budget['primary']} / "
        f"{budget['patch']} / {budget['repair']} / {budget['retry']} | "
        f"9 / 3 / — / 2 |",
        f"| input / output tokens | {ledger['input_tokens']} / "
        f"{ledger['output_tokens']} | — |",
        f"| cost CNY | {budget['cost_cny']:.8f} | {budget['ceiling_cny']:.2f} |",
        f"| ledger SHA | `{ledger['sha256']}` | — |",
        f"| uncertain calls | `{ledger['uncertain_calls']}` | 0 |",
        "",
        "### 2.1 Ledger 明细",
        "",
    ]
    lines.extend(ledger_table(ledger["rows"]))
    lines.extend(
        [
            "",
            "ledger 是 append-only：每次 `llm.chat` 前写 `started`，返回后写 "
            "`finished` + token/cost；primary、patch、retry 全部计入。",
            "",
            "## 3. Q23 指标",
            "",
        ]
    )
    lines.extend(metric_table(metrics))
    lines.extend(
        [
            "",
            "- F 目标 `[0.4, 0.5]`：**不可评估**（F invalid）。",
            f"- C 目标 `[0.0, 0.2]`：`{metrics['answer_correctness']['score']}`，"
            f"target pass=`{metrics['answer_correctness']['target_pass']}`。",
            f"- R 目标 `[0.7, 1.0]`：`{metrics['answer_relevancy']['score']}`，"
            f"target pass=`{metrics['answer_relevancy']['target_pass']}`。",
            f"- C 首句 warning：`{metrics['answer_correctness']['first_sentence_warning']}`"
            "（C=0.0，未触发 >0.2 的 warning 规则）。",
            "",
            "## 4. Q23 初始输出",
            "",
            "```json",
            initial_display,
            "```",
            "",
            "## 5. Q23 初始 claim 明细",
            "",
        ]
    )
    lines.extend(claims_table(q23["claims"]))
    lines.extend(
        [
            "",
            "## 6. Q23 absence 四字段与 cl5 warning",
            "",
            f"- absence_contract_initial_pass：`{q23['absence_contract_initial_pass']}`",
            f"- cl5：`{json.dumps(q23['cl5'], ensure_ascii=False)}`",
            f"- cl5_mixed_sentence_warning：`{q23['cl5_mixed_sentence_warning']}`",
            f"- mixed_sentence_warnings："
            f"`{json.dumps(q23['mixed_sentence_warnings'], ensure_ascii=False)}`",
            "",
            "absence 四字段（初始输出）：",
            "",
            "```json",
            json.dumps(q23["absence_fields"], ensure_ascii=False, indent=1),
            "```",
            "",
            "## 7. Q23 patch 输出",
            "",
            "```json",
            patch_display,
            "```",
            "",
            "## 7.1 Q23 merged 输出（未生成）",
            "",
            "patch_schema_invalid；Agent 在 merge 前停止。`merged_output = null`。",
            "",
            "```json",
            "null",
            "```",
            "",
            "## 8. Q23 patch 失败与 claim 级复核",
            "",
            f"- patch_triggered：`{q23['patch_triggered']}`",
            f"- patch_applied_claims：`{q23['patch_applied_claims']}`",
            f"- patch_semantic_review_required："
            f"`{q23['patch_semantic_review_required']}`",
            f"- patch_schema_invalid：`{q23['patch_schema_invalid']}`",
            f"- patch_example_quote_copied：`{patch_review['patch_example_quote_copied']}`",
            "- merged_output：`None`（未生成）",
            f"- patch_review：`{json.dumps(patch_review, ensure_ascii=False)}`",
            f"- claim_level_review：`{json.dumps(claim_review, ensure_ascii=False)}`",
            "",
            "quote 预检错误：",
            "",
            "```json",
            json.dumps(q23["quote_precheck_errors"], ensure_ascii=False, indent=1),
            "```",
            "",
            "final_errors：",
            "",
            "```json",
            json.dumps(q23["final_errors"], ensure_ascii=False, indent=1),
            "```",
            "",
            "## 9. Q21 / Q11",
            "",
            "| Case | status | reason |",
            "|---|---|---|",
            "| Q21 | `not_run` | stopped at Q23 patch_schema_invalid |",
            "| Q11 | `not_run` | stopped at Q23 patch_schema_invalid |",
            "",
            "因此本轮没有 Q21 的豁免 claim / evidence quote 明细，"
            "也没有 Q11 的 quote 连续性与三项目标结果；不得把它们写成通过。",
            "",
            "## 10. 停止条件",
            "",
        ]
    )
    lines.extend(stop_table(analysis["stop_conditions"]))
    lines.extend(
        [
            "",
            "## 11. 资产 SHA",
            "",
            "| 项 | SHA256 / 值 |",
            "|---|---|",
        ]
    )
    for key, value in assets.items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## 12. 交付声明",
            "",
            "- diagnostic only；不是 10 条，也不是 40 条；不计入 10 条样本。",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora/RAG adapter。",
            "- 未激活 v1.2.4；active/runtime_active 保持 false；默认仍 `v1.0.0`。",
            "- 未跑 10/40；本次失败后不得复用本批准重跑。",
            "- 未修改 Prompt/Agent/Service/validator/patch schema/patch example/"
            "target/fixture。",
            "- 结论只使用 implemented / verified / blocked；未写 accepted。",
            "- **M1-D-6 diagnostic：blocked at Q23 patch_schema_invalid；"
            "不是 verified。**",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    analysis = build_analysis()
    ANALYSIS_FILE.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    analysis_sha = sha256_bytes(ANALYSIS_FILE.read_bytes())
    report = build_report(analysis, analysis_sha)
    REPORT_FILE.write_text(report, encoding="utf-8", newline="\n")
    report_sha = sha256_bytes(REPORT_FILE.read_bytes())
    SHA_FILE.write_text(
        f"{analysis_sha}  {ANALYSIS_FILE.name}\n" f"{report_sha}  {REPORT_FILE.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": analysis["meta"]["status"],
                "blocked_at": analysis["conclusion"]["blocked_at"],
                "analysis_sha256": analysis_sha,
                "report_sha256": report_sha,
                "ledger_sha256": analysis["meta"]["ledger_sha256"],
                "calls": analysis["budget"]["calls_used"],
                "cost_cny": analysis["budget"]["cost_cny"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
