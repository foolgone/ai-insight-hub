"""M1-D-1 r3 approved 10-case Judge-only Production Service replay.

This script uses the real C3 Service path:

    rag_judge_service.judge_trace(session=None, trace=synthetic RagTrace,
                                  item=synthetic item, prompt_version="v1.2.0")

It does not create a RagEvaluationRun, does not call WeKnora, and does not
write DB rows. The driver only aggregates JudgeOutcome values.

Run from backend/ with the approved DASHSCOPE_API_KEY present:
    ..\\backend\\venv\\Scripts\\python.exe docs/repair/phase3e/m1d1_run_judge_only.py
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Temporary process-local endpoint override for the approved qwen-max replay.
# Do not write these values to .env.
if not os.environ.get("DASHSCOPE_API_KEY"):
    raise SystemExit("DASHSCOPE_API_KEY is required for the approved qwen-max replay")
os.environ["DEEPSEEK_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
os.environ["DEEPSEEK_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
os.environ["DEFAULT_LLM_MODEL"] = "qwen-max"
os.environ["DEFAULT_TEMPERATURE"] = "0.0"
os.environ["RAG_JUDGE_MAX_TOKENS"] = "8192"

from app.core.config import settings  # noqa: E402
from app.core.llm import LLMClient  # noqa: E402
from app.models.rag import RagTrace  # noqa: E402
from app.services.rag_judge_service import judge_trace  # noqa: E402

BASE = Path(__file__).resolve().parents[3]
APPLICATION_FILE = BASE / "docs/repair/phase3e/m1d1-ten-case-application.json"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.0/MANIFEST.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.0"
OUT_JSON = BASE / "docs/repair/phase3e/m1d1-judge-only-results.json"
OUT_MD = BASE / "docs/repair/29-m1d1-judge-only-results.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d1-judge-only-results.sha256"

EXPECTED_APPLICATION_SHA = "7378d368adf13b7d55e58904af200310fa20f47cf51ccc67967f13e7e437e2ad"
EXPECTED_FIXTURE_SHA = "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"
EXPECTED_MANIFEST_SHA = "ee1c25be8767bf66069f92e769fd8dd1d986cb950d9e96d3f550af587c35f778"
EXPECTED_PROMPT_SHA = {
    "faithfulness.txt": "b637775869163fdd7bd2545ca9b79197c10193d2937c9bef4e61add72e934d61",
    "answer_correctness.txt": "a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95",
    "answer_relevancy.txt": "a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88",
}
HG_CASES = {"Q23", "Q35", "Q36"}
RUNS_PER_HG = 3
MAX_JUDGE_CALLS = 51
CEILING_CNY = 1.00
PRICE_INPUT = 0.0024 / 1000
PRICE_OUTPUT = 0.0096 / 1000
FIXED_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "m1d1:judge-only:user")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cost_cny(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * PRICE_INPUT + output_tokens * PRICE_OUTPUT


def in_target(value: float | None, target: Any) -> bool:
    if value is None or not isinstance(target, list) or len(target) != 2:
        return False
    return float(target[0]) <= float(value) <= float(target[1])


def case_target_status(
    app_case: dict[str, Any],
    case_result: dict[str, Any],
) -> str:
    runs = case_result.get("runs") or []
    if not runs:
        return "BLOCKED"
    case_id = app_case["case_id"]
    targets = app_case["targets"]
    if case_id == "Q29":
        f = next(
            (o for o in runs[0]["outcomes"] if o["metric_name"] == "faithfulness"),
            None,
        )
        if f is None or f["status"] != "skipped" or f["skipped_reason"] != "no_scorable_claims":
            return "FAIL"
        for metric in ("answer_correctness", "answer_relevancy"):
            outcome = next(
                (o for o in runs[0]["outcomes"] if o["metric_name"] == metric),
                None,
            )
            if outcome is None or not in_target(outcome["score"], targets.get(metric)):
                return "FAIL"
        return "PASS"

    for target_metric in ("faithfulness", "answer_correctness", "answer_relevancy"):
        if target_metric not in targets:
            continue
        if case_id == "Q36" and target_metric == "answer_correctness":
            continue
        pass_count = sum(
            1
            for run in runs
            if in_target(
                next(
                    (o["score"] for o in run["outcomes"] if o["metric_name"] == target_metric),
                    None,
                ),
                targets[target_metric],
            )
        )
        required = 3 if case_id == "Q23" else (2 if case_id in HG_CASES else 1)
        if pass_count < required:
            return "FAIL"
    return "PASS"


def baseline_metrics(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outcomes = case["arms"]["v1.1.5"]["outcomes"]
    return {
        item["metric"]: {
            "status": item["status"],
            "score": item.get("score"),
            "skipped_reason": item.get("skipped_reason"),
        }
        for item in outcomes
    }


def synthetic_trace(case: dict[str, Any]) -> RagTrace:
    case_id = case["id"]
    return RagTrace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"m1d1:judge-only:{case_id}"),
        user_id=FIXED_USER_ID,
        dataset_item_id=None,
        task_id=None,
        idempotency_key=None,
        adapter="fixture",
        mode="query",
        context_source="agent_chat",
        query=case["question"],
        answer=case["answer"],
        retrieved_contexts=[{"content": ctx["content"]} for ctx in case["contexts"]],
        status="success",
    )


def outcome_payload(outcome: Any) -> dict[str, Any]:
    return {
        "metric_name": outcome.metric_name,
        "metric_version": outcome.metric_version,
        "status": outcome.status,
        "score": outcome.score,
        "skipped_reason": outcome.skipped_reason,
        "invalid_reason": outcome.invalid_reason,
        "error_type": outcome.error_type,
        "error_message": outcome.error_message,
        "latency_ms": outcome.latency_ms,
        "judge_config": dict(outcome.judge_config or {}),
        "details": dict(outcome.details or {}),
        "raw_output": outcome.raw_output,
        "raw_truncated": outcome.raw_truncated,
    }


def calls_for(outcomes: list[Any]) -> int:
    return sum(
        1
        for outcome in outcomes
        if outcome.metric_name != "faithfulness_strict"
        and not (outcome.status == "skipped" and outcome.latency_ms == 0)
    )


def usage_for(outcomes: list[Any]) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for outcome in outcomes:
        if outcome.metric_name == "faithfulness_strict":
            continue
        usage = (outcome.details or {}).get("token_usage") or {}
        input_tokens += int(usage.get("input") or 0)
        output_tokens += int(usage.get("output") or 0)
    return input_tokens, output_tokens


def primary_metrics(outcomes: list[Any]) -> dict[str, Any]:
    by_name = {outcome.metric_name: outcome for outcome in outcomes}
    result: dict[str, Any] = {}
    for metric in ("faithfulness", "faithfulness_strict", "answer_correctness", "answer_relevancy"):
        outcome = by_name.get(metric)
        if outcome is None:
            continue
        result[metric] = {
            "status": outcome.status,
            "score": outcome.score,
            "skipped_reason": outcome.skipped_reason,
            "invalid_reason": outcome.invalid_reason,
        }
    return result


def validate_fingerprint(outcomes: list[Any]) -> list[str]:
    errors: list[str] = []
    for outcome in outcomes:
        config = outcome.judge_config or {}
        if config.get("prompt_version") != "v1.2.0":
            errors.append(f"prompt_version={config.get('prompt_version')!r}")
        if config.get("schema_version") != "rag_judge_schema_v3":
            errors.append(f"schema_version={config.get('schema_version')!r}")
        if config.get("metric_version") != "v3":
            errors.append(f"metric_version={config.get('metric_version')!r}")
        if config.get("temperature") not in (0.0, 0):
            errors.append(f"temperature={config.get('temperature')!r}")
        if config.get("max_tokens") != 8192:
            errors.append(f"max_tokens={config.get('max_tokens')!r}")
        if config.get("model") not in (None, "qwen-max"):
            errors.append(f"model={config.get('model')!r}")
        if outcome.metric_name != "faithfulness_strict":
            expected = {
                "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
                "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
                "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
            }.get(outcome.metric_name)
            if expected and config.get("prompt_sha256") != expected:
                errors.append(
                    f"{outcome.metric_name} prompt_sha256={config.get('prompt_sha256')!r}"
                )
    return errors


async def preflight() -> dict[str, Any]:
    application_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    manifest_sha = sha256_bytes(MANIFEST_FILE.read_bytes())
    manifest = load_json(MANIFEST_FILE)
    prompt_sha = {
        name: sha256_bytes((PROMPT_DIR / name).read_bytes()) for name in EXPECTED_PROMPT_SHA
    }
    errors: list[str] = []
    if application_sha != EXPECTED_APPLICATION_SHA:
        errors.append(f"application_sha={application_sha}")
    if fixture_sha != EXPECTED_FIXTURE_SHA:
        errors.append(f"fixture_sha={fixture_sha}")
    if manifest_sha != EXPECTED_MANIFEST_SHA:
        errors.append(f"manifest_sha={manifest_sha}")
    if prompt_sha != EXPECTED_PROMPT_SHA:
        errors.append(f"prompt_sha={prompt_sha}")
    if manifest.get("status") != "frozen" or manifest.get("active") is not False:
        errors.append("manifest is not frozen/inactive")
    if settings.DEFAULT_LLM_MODEL != "qwen-max":
        errors.append(f"model={settings.DEFAULT_LLM_MODEL!r}")
    if settings.DEFAULT_TEMPERATURE != 0.0:
        errors.append(f"temperature={settings.DEFAULT_TEMPERATURE!r}")
    if settings.RAG_JUDGE_MAX_TOKENS != 8192:
        errors.append(f"max_tokens={settings.RAG_JUDGE_MAX_TOKENS!r}")
    if settings.RAG_JUDGE_PROMPT_VERSION != "v1.0.0":
        errors.append(f"default_prompt_version={settings.RAG_JUDGE_PROMPT_VERSION!r}")

    preflight_usage = {"input": 0, "output": 0}
    if not errors:
        async with LLMClient() as llm:
            response = await llm.chat(
                [{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            preflight_usage = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            }
    return {
        "application_sha256": application_sha,
        "fixture_sha256": fixture_sha,
        "manifest_sha256": manifest_sha,
        "prompt_sha256": prompt_sha,
        "model": settings.DEFAULT_LLM_MODEL,
        "temperature": settings.DEFAULT_TEMPERATURE,
        "max_tokens": settings.RAG_JUDGE_MAX_TOKENS,
        "default_prompt_version": settings.RAG_JUDGE_PROMPT_VERSION,
        "preflight_usage": preflight_usage,
        "errors": errors,
    }


async def main() -> None:
    application = load_json(APPLICATION_FILE)
    fixture = load_json(FIXTURE_FILE)
    preflight_result = await preflight()
    expected_ids = [case["case_id"] for case in application["cases"]]
    by_id = {case["id"]: case for case in fixture["cases"]}
    fixture_ids = [case_id for case_id in expected_ids if case_id in by_id]

    results: dict[str, Any] = {
        "meta": {
            "name": "m1d1-judge-only-results",
            "kind": "judge_only_production_service_replay_not_end_to_end",
            "date": "2026-11-21",
            "application_revision": application["meta"]["revision"],
            "application_sha256": preflight_result["application_sha256"],
            "fixture_sha256": preflight_result["fixture_sha256"],
            "manifest_sha256": preflight_result["manifest_sha256"],
            "prompt_sha256": preflight_result["prompt_sha256"],
            "target_sha256": application["meta"]["target_sha256"],
            "labels_sha256": application["meta"]["labels_sha256"],
            "judge_run": True,
            "created_run": False,
            "wrote_db": False,
            "runtime_activated": False,
            "default_prompt_version": preflight_result["default_prompt_version"],
            "preflight": preflight_result,
        },
        "cases": [],
        "runs": [],
        "totals": {
            "case_runs": 0,
            "judge_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_cny": 0.0,
            "preflight_input_tokens": preflight_result["preflight_usage"]["input"],
            "preflight_output_tokens": preflight_result["preflight_usage"]["output"],
            "ceiling_cny": CEILING_CNY,
            "max_judge_calls": MAX_JUDGE_CALLS,
        },
        "stop_triggered": False,
        "stop_reason": None,
        "gate": {"passed": False, "failures": []},
    }

    if preflight_result["errors"]:
        results["stop_triggered"] = True
        results["stop_reason"] = "preflight: " + "; ".join(preflight_result["errors"])
    elif fixture_ids != expected_ids:
        results["stop_triggered"] = True
        results["stop_reason"] = f"fixture cases missing: {fixture_ids}"
    else:
        total_calls = 0
        total_input = 0
        total_output = 0
        for case in application["cases"]:
            case_id = case["case_id"]
            source = by_id[case_id]
            baseline = baseline_metrics(source)
            runs: list[dict[str, Any]] = []
            repeat_count = RUNS_PER_HG if case_id in HG_CASES else 1
            for run_index in range(1, repeat_count + 1):
                if total_calls + 3 > MAX_JUDGE_CALLS:
                    results["stop_triggered"] = True
                    results[
                        "stop_reason"
                    ] = f"budget: next case-run would exceed {MAX_JUDGE_CALLS} calls"
                    break
                trace = synthetic_trace(source)
                item = SimpleNamespace(gold_answer=source["gold_answer"])
                outcomes = await judge_trace(
                    session=None,
                    trace=trace,
                    item=item,
                    prompt_version="v1.2.0",
                )
                fingerprint_errors = validate_fingerprint(outcomes)
                calls = calls_for(outcomes)
                input_tokens, output_tokens = usage_for(outcomes)
                total_calls += calls
                total_input += input_tokens
                total_output += output_tokens
                run_cost = cost_cny(input_tokens, output_tokens)
                run_record = {
                    "case_id": case_id,
                    "run_index": run_index,
                    "repeat_count": repeat_count,
                    "calls": calls,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_cny": round(run_cost, 8),
                    "fingerprint_errors": fingerprint_errors,
                    "outcomes": [outcome_payload(outcome) for outcome in outcomes],
                }
                results["runs"].append(run_record)
                runs.append(run_record)

                statuses = {outcome.metric_name: outcome for outcome in outcomes}
                bad = [outcome for outcome in outcomes if outcome.status in {"invalid", "failed"}]
                f_outcome = statuses.get("faithfulness")
                if bad:
                    results["stop_triggered"] = True
                    results["stop_reason"] = f"{case_id} run {run_index}: " + ", ".join(
                        f"{outcome.metric_name}={outcome.status}"
                        f"({outcome.invalid_reason or outcome.error_type})"
                        for outcome in bad
                    )
                elif fingerprint_errors:
                    results["stop_triggered"] = True
                    results[
                        "stop_reason"
                    ] = f"{case_id} run {run_index}: fingerprint: " + "; ".join(fingerprint_errors)
                elif case_id == "Q29" and (
                    f_outcome is None
                    or f_outcome.status != "skipped"
                    or f_outcome.skipped_reason != "no_scorable_claims"
                ):
                    results["stop_triggered"] = True
                    results["stop_reason"] = (
                        f"Q29 F must be skipped(no_scorable_claims), got "
                        f"{getattr(f_outcome, 'status', None)}"
                    )
                elif f_outcome is not None and f_outcome.details.get("validation_errors"):
                    results["stop_triggered"] = True
                    results["stop_reason"] = (
                        f"{case_id} run {run_index}: F validation_errors="
                        f"{f_outcome.details.get('validation_errors')}"
                    )

                if not results["stop_triggered"]:
                    for metric, current in primary_metrics(outcomes).items():
                        if metric == "faithfulness_strict" or current["score"] is None:
                            continue
                        old = baseline.get(metric)
                        if (
                            old is None
                            or old.get("status") != "evaluated"
                            or old.get("score") is None
                        ):
                            continue
                        if case_id == "Q17" and metric == "faithfulness":
                            continue  # explained by policy_relationship reclassification
                        if case_id == "Q36" and metric == "answer_correctness":
                            continue  # diagnostic only
                        if float(old["score"]) - float(current["score"]) > 0.10 + 1e-9:
                            results["stop_triggered"] = True
                            results["stop_reason"] = (
                                f"{case_id} run {run_index}: {metric} drop "
                                f"{old['score']} -> {current['score']} > 0.10"
                            )
                            break

                if (
                    total_calls > MAX_JUDGE_CALLS
                    or cost_cny(total_input, total_output) > CEILING_CNY
                ):
                    results["stop_triggered"] = True
                    results["stop_reason"] = (
                        f"budget: calls={total_calls}, "
                        f"cost={cost_cny(total_input, total_output):.6f}"
                    )

                if results["stop_triggered"]:
                    break
            results["cases"].append(
                {
                    "case_id": case_id,
                    "group": case["group"],
                    "final_category": case["final_category"],
                    "targets": case["targets"],
                    "baseline": baseline,
                    "runs": runs,
                }
            )
            if results["stop_triggered"]:
                break

    results["totals"].update(
        {
            "case_runs": len(results["runs"]),
            "judge_calls": sum(run["calls"] for run in results["runs"]),
            "input_tokens": sum(run["input_tokens"] for run in results["runs"]),
            "output_tokens": sum(run["output_tokens"] for run in results["runs"]),
            "cost_cny": round(
                sum(run["cost_cny"] for run in results["runs"]),
                8,
            ),
        }
    )

    # Gate evaluation only when all 10 primary cases have at least one run and no stop.
    primary_cases = {case["case_id"]: case for case in results["cases"]}
    if not results["stop_triggered"] and set(primary_cases) == set(expected_ids):
        failures: list[str] = []
        for case in application["cases"]:
            case_id = case["case_id"]
            entry = primary_cases[case_id]
            runs = entry["runs"]
            targets = case["targets"]
            if case_id == "Q29":
                f_status = next(
                    (o for o in runs[0]["outcomes"] if o["metric_name"] == "faithfulness"),
                    None,
                )
                if (
                    f_status is None
                    or f_status["status"] != "skipped"
                    or f_status["skipped_reason"] != "no_scorable_claims"
                ):
                    failures.append(f"{case_id}: F not skipped(no_scorable_claims)")
                for metric in ("answer_correctness", "answer_relevancy"):
                    outcome = next(
                        (o for o in runs[0]["outcomes"] if o["metric_name"] == metric),
                        None,
                    )
                    if outcome is None or not in_target(outcome["score"], targets.get(metric)):
                        failures.append(f"{case_id}: {metric} target miss")
                continue

            metrics = {
                "faithfulness": "faithfulness",
                "answer_correctness": "answer_correctness",
                "answer_relevancy": "answer_relevancy",
            }
            for target_metric, outcome_name in metrics.items():
                if target_metric not in targets:
                    continue
                if case_id == "Q36" and target_metric == "answer_correctness":
                    continue  # diagnostic only
                pass_count = 0
                for run in runs:
                    outcome = next(
                        (o for o in run["outcomes"] if o["metric_name"] == outcome_name),
                        None,
                    )
                    if outcome is not None and in_target(outcome["score"], targets[target_metric]):
                        pass_count += 1
                required = 3 if case_id == "Q23" else (2 if case_id in HG_CASES else 1)
                if pass_count < required:
                    failures.append(
                        f"{case_id}: {target_metric} {pass_count}/{len(runs)} "
                        f"< required {required}"
                    )
        results["gate"] = {"passed": not failures, "failures": failures}
    elif not results["stop_triggered"]:
        results["stop_triggered"] = True
        results["stop_reason"] = "unprocessed: not all 10 primary cases completed"

    results["meta"]["status"] = (
        "passed"
        if results["gate"]["passed"] and not results["stop_triggered"]
        else ("stopped" if results["stop_triggered"] else "failed")
    )
    results["meta"]["verified"] = results["meta"]["status"] == "passed"
    OUT_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    OUT_SHA.write_text(
        f"{sha256_bytes(OUT_JSON.read_bytes())}  {OUT_JSON.name}\n",
        encoding="utf-8",
        newline="\n",
    )

    lines = [
        "# M1-D-1 Judge-only Production Service replay 结果",
        "",
        f"> 状态：`{results['meta']['status']}`；"
        f"application `{results['meta']['application_revision']}`；"
        "未创建 Run、未写 DB、未激活 v1.2.0。",
        f"> fixture SHA：`{results['meta']['fixture_sha256']}`",
        f"> MANIFEST SHA：`{results['meta']['manifest_sha256']}`",
        f"> 结果 JSON SHA：`{sha256_bytes(OUT_JSON.read_bytes())}`",
        "",
        "## 1. 10 条结果",
        "",
        "| Case | group | F | F_strict | C | R | target pass | status |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    app_by_id = {case["case_id"]: case for case in application["cases"]}
    for case in results["cases"]:
        run = case["runs"][0]
        by_name = {o["metric_name"]: o for o in run["outcomes"]}
        f = by_name.get("faithfulness") or {}
        fs = by_name.get("faithfulness_strict") or {}
        c = by_name.get("answer_correctness") or {}
        r = by_name.get("answer_relevancy") or {}
        lines.append(
            f"| {case['case_id']} | {case['group']} | "
            f"{f.get('score', f.get('status'))} | {fs.get('score', fs.get('status'))} | "
            f"{c.get('score', c.get('status'))} | {r.get('score', r.get('status'))} | "
            f"{case_target_status(app_by_id[case['case_id']], case)} | {f.get('status')} |"
        )
    lines.extend(
        [
            "",
            "## 2. HG 三次结果",
            "",
            "| Case | run | F | F_strict | C | R |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for case in results["cases"]:
        if case["case_id"] not in HG_CASES:
            continue
        for run in case["runs"]:
            by_name = {o["metric_name"]: o for o in run["outcomes"]}
            lines.append(
                f"| {case['case_id']} | {run['run_index']} | "
                f"{by_name.get('faithfulness', {}).get('score', '—')} | "
                f"{by_name.get('faithfulness_strict', {}).get('score', '—')} | "
                f"{by_name.get('answer_correctness', {}).get('score', '—')} | "
                f"{by_name.get('answer_relevancy', {}).get('score', '—')} |"
            )
    lines.extend(
        [
            "",
            "### 2.1 HG median / min / max",
            "",
            "| Case | metric | median | min | max |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for case in results["cases"]:
        if case["case_id"] not in HG_CASES:
            continue
        for metric in (
            "faithfulness",
            "faithfulness_strict",
            "answer_correctness",
            "answer_relevancy",
        ):
            values = [
                next(
                    (
                        o["score"]
                        for o in run["outcomes"]
                        if o["metric_name"] == metric and isinstance(o["score"], (int, float))
                    ),
                    None,
                )
                for run in case["runs"]
            ]
            numeric = [float(value) for value in values if value is not None]
            if not numeric:
                continue
            lines.append(
                f"| {case['case_id']} | {metric} | {statistics.median(numeric):.6f} | "
                f"{min(numeric):.6f} | {max(numeric):.6f} |"
            )
    lines.extend(
        [
            "",
            "## 3. Q36 C base/variant（诊断）",
            "",
            "| run | C actual | base 0.5–0.6 | variant 0.9–1.0 |",
            "|---:|---:|---|---|",
        ]
    )
    q36 = primary_cases.get("Q36")
    if q36:
        for run in q36["runs"]:
            c = next(
                (o for o in run["outcomes"] if o["metric_name"] == "answer_correctness"),
                None,
            )
            value = c["score"] if c else None
            lines.append(
                f"| {run['run_index']} | {value} | "
                f"{'in' if in_target(value, [0.5, 0.6]) else 'out'} | "
                f"{'in' if in_target(value, [0.9, 1.0]) else 'out'} |"
            )
    totals = results["totals"]
    lines.extend(
        [
            "",
            "## 4. 调用与成本",
            "",
            "| 项 | 实际 | 预算/上限 |",
            "|---|---:|---:|",
            f"| case-runs | {totals['case_runs']} | 16 |",
            f"| Judge calls | {totals['judge_calls']} | 51 |",
            f"| input tokens | {totals['input_tokens']} | 198,900 |",
            f"| output tokens | {totals['output_tokens']} | 29,410 |",
            f"| cost CNY | {totals['cost_cny']:.6f} | 1.00 |",
            f"| preflight tokens | {totals['preflight_input_tokens']} / "
            f"{totals['preflight_output_tokens']} | — |",
            "",
            "## 5. 停止与门禁",
            "",
            f"- stop_triggered：`{results['stop_triggered']}`",
            f"- stop_reason：{results['stop_reason'] or '—'}",
            f"- gate passed：`{results['gate']['passed']}`",
            f"- gate failures：{results['gate']['failures'] or '—'}",
            "",
            "## 6. 边界",
            "",
            "- 通过 `rag_judge_service.judge_trace(session=None, ...)` 执行；",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora；",
            "- 未激活 v1.2.0、未改默认版本/Prompt；",
            "- 未跑 40、未启动 M2/M3；",
            f"- verified：`{results['meta']['verified']}`；accepted 仍需人工决定。",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": results["meta"]["status"],
                "verified": results["meta"]["verified"],
                "stop_triggered": results["stop_triggered"],
                "stop_reason": results["stop_reason"],
                "gate_passed": results["gate"]["passed"],
                "gate_failures": results["gate"]["failures"],
                "totals": totals,
                "output_sha256": sha256_bytes(OUT_JSON.read_bytes()),
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
