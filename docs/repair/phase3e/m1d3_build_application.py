"""Build the M1-D-3 v1.2.1 10-case Judge application from the r3 shape."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
SOURCE = BASE / "docs/repair/phase3e/m1d1-ten-case-application.json"
OUT = BASE / "docs/repair/phase3e/m1d3-ten-case-application.json"

PROMPT_VERSION = "v1.2.1"
MANIFEST_SHA = "8bdd673cd44ed772dfc1630280e571d4cdd8ed786066eb72eb553a9be8b0b278"
PROMPT_SHA = {
    "faithfulness.txt": "9efdc64df1eebafa727bc0946a03192c2d9e9907bd7a3170f867f19774211068",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
FIXTURE_SHA = "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    app = load_json(SOURCE)
    app["meta"].update(
        {
            "name": "m1d3-ten-case-judge-application",
            "status": "pending_approval",
            "revision": "r4",
            "application_target": PROMPT_VERSION,
            "previous_application": "m1d1 r3 (v1.2.0) — not reused",
            "previous_review": "new_application_after_v1.2.1_freeze",
            "not_reusing_previous_approval": True,
            "date": "2026-11-22",
            "design_commit": "916e60a",
            "header_fix_commit": "27bf5fc",
            "freeze_commit": "3f4d580",
            "freeze_record": "docs/repair/32-m1d2-v1.2.1-freeze-record.md",
            "prompt_version": PROMPT_VERSION,
            "prompt_status": "frozen",
            "prompt_active": False,
            "manifest_sha256": MANIFEST_SHA,
            "prompt_sha256": PROMPT_SHA,
            "rubric_version": "v1.2.0",
            "metric_version": "v3",
            "fixture_file": "docs/repair/phase3e/pilot-10-v1.1.5-gate.json",
            "fixture_sha256": FIXTURE_SHA,
            "not_approved": True,
            "judge_run": False,
            "runtime_activated": False,
        }
    )
    app["meta"]["revision_notes"] = [
        "v1.2.1 frozen Prompt；F 9efdc64d… / C a50520de… / R a5386070…；MANIFEST 8bdd673c…",
        "rubric_version=v1.2.0；Schema v3 / Metric v3；target v1.0.2 未重算",
        "Judge-only fixed fixture；production Service replay via judge_trace(session=None)",
        "Q11 bad 非连续 quote -> invalid(contract_violation)+quote_not_found；"
        "good 连续 quote -> evaluated 1.0",
        "Q36 C base/variant 双报，不参与 PASS/FAIL；Q23 3/3、Q35/Q36 >=2/3；" "最多 51 calls / CNY 1.00",
        "不复用 v1.2.0 的 10 条批准；未跑 Judge",
    ]
    app["meta"]["q11_evidence"] = {
        "fixture_sha256": FIXTURE_SHA,
        "bad": {
            "quote": ("订单签收后 7 天内可申请无理由退款。" "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"),
            "expected": {
                "status": "invalid",
                "invalid_reason": "contract_violation",
                "error_code": "quote_not_found",
            },
        },
        "good": {
            "claim": "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。",
            "claim_type": "factual_claim",
            "claim_subtype": "condition",
            "support_status": "supported",
            "quote": "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。",
            "expected": {"status": "evaluated", "score": 1.0},
        },
        "tests": [
            "test_v121_bad_noncontiguous_quote_is_invalid",
            "test_v121_good_contiguous_quote_is_supported",
        ],
    }

    config = app["run_config"]
    config["judge_prompt_version"] = PROMPT_VERSION
    config["rubric_version"] = "v1.2.0"
    config["execution_vehicle"] = config["execution_vehicle"].replace("v1.2.0", PROMPT_VERSION)
    config["default_prompt_version"] = "v1.0.0"
    config["fixture"]["file"] = "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
    config["fixture"]["sha256"] = FIXTURE_SHA
    config["fixture"]["note"] = (
        "fixed v1.1.5 10-case gate answer/contexts/gold; no WeKnora, no retrieval, "
        "no new answer generation; fixture target field is historical, "
        "v1.0.2 target is authoritative"
    )
    config["env"]["RAG_JUDGE_PROMPT_VERSION"] = "v1.0.0"

    for item in app["stop_conditions"]:
        item["condition"] = item["condition"].replace("v1.2.0", PROMPT_VERSION)
        item["action"] = item["action"].replace("v1.2.0", PROMPT_VERSION)
    app["stop_conditions"].append(
        {
            "code": "q11_quote_continuity",
            "condition": "Q11 非连续 quote 未被 Service 判 invalid，或 good 连续 quote 未 evaluated",
            "action": "立即停止；不得放宽 Service 或改 fixture",
        }
    )

    app["report_requirements"] = [
        "使用 docs/repair/phase3e/m1c-c4-report-template.md",
        "逐条报告 status、F_coverage、F_strict（仅诊断）、C、R、"
        "invalid/skipped/failed、insufficient_count/ratio、known issue",
        "逐条写 PASS/FAIL/BLOCKED；Q29 只能按 skipped 语义判定",
        "HG 3 条（Q23/Q35/Q36）与 provisional 7 条分开，不混算均值",
        "Q17 标 policy_relationship_target_reapproval；Q35/Q36 标 old run only",
        "报告写 prompt_version=v1.2.1、rubric_version=v1.2.0、F/C/R SHA、"
        "MANIFEST SHA、fixture SHA、target SHA",
        "报告写 model/temperature/max_tokens 与 judge_trace production Service replay 方法",
        "Q23/Q35/Q36 报告 3 次全部结果、median/min/max，不报最好一次",
        "Q36 的 C 同时报 base 0.5–0.6 与 variant 0.9–1.0，只作诊断，不参与 PASS/FAIL",
        "报告 Q11 bad/good 结果：invalid(contract_violation)+quote_not_found / evaluated 1.0",
        "结论只能写 implemented/verified/blocked；不得自行写 accepted",
    ]
    app["boundaries"] = [
        "本文件是 v1.2.1 新申请材料，不是 Judge 运行；未调用模型、未创建 Run",
        "方法 A：Judge-only 固定 pilot answer/contexts/gold；不调用 WeKnora、不做检索、不生成新答案",
        "执行载体：rag_judge_service.judge_trace(session=None, synthetic RagTrace, "
        "item, prompt_version=v1.2.1)",
        "不复用 v1.2.0 的 10 条批准；本申请必须重新批准",
        "不激活 v1.2.1；active 保持 false、runtime_active 保持 false；默认仍 v1.0.0",
        "不修改 Prompt、MANIFEST、Schema、Service、API、DB、migration 022、r2、target v1.0.2、Q11 fixture",
        "不运行 40 条；10 条通过后才可单独申请 40 条",
        "不启动 M2/M3；不把 M1-C/M1-D 标 accepted",
    ]
    app["approval_items"] = [
        "确认这是 v1.2.1 新申请，不复用 v1.2.0 批准",
        "确认 prompt_version=v1.2.1、F 9efdc64d…、C a50520de…、R a5386070…、MANIFEST 8bdd673c…",
        "确认 rubric_version=v1.2.0、Schema v3、Metric v3、target v1.0.2",
        "确认 Q11 bad/good 证据与 Service invalid 契约",
        "确认 Judge-only fixture、Q36 C 双报、HG 重复与 51 次预算",
        "确认停止条件与失败处理",
        "确认不会激活 v1.2.1、不会改默认版本、不会跑 40",
        "批准后才执行 10 条；执行后停下报告",
    ]

    OUT.write_text(
        json.dumps(app, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": OUT.name,
                "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
                "revision": app["meta"]["revision"],
                "prompt_version": app["meta"]["prompt_version"],
                "case_count": app["case_summary"]["case_count"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
