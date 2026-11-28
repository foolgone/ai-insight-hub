"""M1-D-4 v1.2.2 Q23/Q21/Q11 single-case diagnostic run.

Approved single-case diagnostic:
- 3 cases x 1 run x 3 metrics = 9 primary Judge calls
- 3 repair reserve + 2 retry reserve
- max 14 Judge calls / CNY 0.30
- judge_trace(session=None, ...) only; no RagEvaluationRun, no DB write,
  no WeKnora/RAG adapter, no v1.2.2 activation.

Run from backend/ with the approved DASHSCOPE_API_KEY present:
    ..\\backend\\venv\\Scripts\\python.exe docs/repair/phase3e/m1d4_run_single_case.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BASE = Path(__file__).resolve().parents[3]
if str(BASE / "backend") not in sys.path:
    sys.path.insert(0, str(BASE / "backend"))

if not os.environ.get("DASHSCOPE_API_KEY"):
    raise SystemExit("DASHSCOPE_API_KEY is required for the approved qwen-max replay")
os.environ["DEEPSEEK_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
os.environ["DEEPSEEK_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
os.environ["DEFAULT_LLM_MODEL"] = "qwen-max"
os.environ["DEFAULT_TEMPERATURE"] = "0.0"
os.environ["RAG_JUDGE_MAX_TOKENS"] = "8192"

from app.agents.rag_judge_agent import (  # noqa: E402
    RagJudgeAgent,
    load_judge_prompt,
)
from app.core.config import settings  # noqa: E402
from app.core.llm import LLMClient  # noqa: E402
from app.models.rag import RagTrace  # noqa: E402
from app.services.rag_judge_service import judge_trace  # noqa: E402

APPLICATION_FILE = BASE / "docs/repair/phase3e/m1d4-single-case-diagnostic-application.json"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.2/MANIFEST.json"
VALIDATION_FILE = BASE / "docs/repair/phase3e/m1d4-prompt-v1.2.2-validation.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.2"
OUT_JSON = BASE / "docs/repair/phase3e/m1d4-single-case-results.json"
OUT_MD = BASE / "docs/repair/39-m1d4-v1.2.2-single-case-diagnostic-results.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d4-single-case-results.sha256"

EXPECTED_APPLICATION_SHA = "a38e6477558ee8c6e0e2c4450170406edcfe31f012f78dd604a36a642db9bf19"
EXPECTED_FIXTURE_SHA = "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"
EXPECTED_TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
EXPECTED_LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
EXPECTED_MANIFEST_SHA = "81dd3a3219f6f2437b83264e1fd28d74db05c243e3335b9ce321bac9dbb22f5d"
EXPECTED_VALIDATION_SHA = "fadef85639363bccf67e0052e0b36fcf780b970fb177d67d992f59c8b380e2f8"
EXPECTED_PROMPT_SHA = {
    "faithfulness.txt": ("ed21979abd71dedd522ee97636b17509bae9d1b845d54fa114f4a1fbf8f01cf3"),
    "answer_correctness.txt": ("a50520de0122216c9238d23c110967c3bbe259586ef24db100ee874a4ce35e95"),
    "answer_relevancy.txt": ("a5386070407381098bcc14fc8c67a8853f94ebaa91d188e473ef92237dc58d88"),
}
EXPECTED_REPAIR_SHA = "7541fe3f4d079f2c173ae6347a247b9614de14f30f761d216c1267bc4a591869"
EXPECTED_AGENT_COMMIT = "2ef9200"
EXPECTED_FREEZE_COMMIT = "159880b"
PROMPT_VERSION = "v1.2.2"
CASE_IDS = ("Q23", "Q21", "Q11")
MAX_JUDGE_CALLS = 14
CEILING_CNY = 0.30
PRICE_INPUT = 0.0024 / 1000
PRICE_OUTPUT = 0.0096 / 1000
FIXED_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "m1d4:single-case:user")
ABSENCE_MARKERS = ("未提及", "未说明", "未规定", "未涉及", "没有提及", "没有说明")
EXEMPTION_MARKERS = ("不受", "不适用", "除外", "例外", "仍可", "可以申请")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cost_cny(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * PRICE_INPUT + output_tokens * PRICE_OUTPUT


def in_target(value: float | None, target: Any) -> bool:
    if value is None or not isinstance(target, list) or len(target) != 2:
        return False
    return float(target[0]) <= float(value) <= float(target[1])


def normalized(text: str) -> str:
    return "".join(str(text).split())


class BudgetExceeded(RuntimeError):
    """Raised before a Judge call that would exceed the approved budget."""


@dataclass
class CallRecorder:
    max_calls: int = MAX_JUDGE_CALLS
    calls: list[dict[str, Any]] = field(default_factory=list)
    judge_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def start_call(
        self,
        *,
        case_id: str,
        metric: str,
        kind: str,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        prompt_version: str,
        prompt_sha256: str,
        system_head: str,
        original_raw: str | None = None,
        validation_error: str | None = None,
    ) -> int:
        if self.judge_calls >= self.max_calls:
            raise BudgetExceeded(f"budget: judge_calls={self.judge_calls} >= {self.max_calls}")
        self.judge_calls += 1
        index = len(self.calls)
        self.calls.append(
            {
                "call_index": self.judge_calls,
                "case_id": case_id,
                "metric": metric,
                "kind": kind,
                "model_requested": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "prompt_version": prompt_version,
                "prompt_sha256": prompt_sha256,
                "system_head": system_head,
                "original_raw": original_raw,
                "validation_error": validation_error,
                "content": None,
                "response_model": None,
                "usage": None,
                "latency_ms": None,
                "error": None,
            }
        )
        return index

    def finish_call(
        self,
        index: int,
        *,
        content: str | None = None,
        response_model: str | None = None,
        usage: Any = None,
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        record = self.calls[index]
        record["content"] = content
        record["response_model"] = response_model
        record["latency_ms"] = latency_ms
        record["error"] = error
        if usage is not None:
            record["usage"] = {
                "input": usage.input_tokens,
                "output": usage.output_tokens,
            }
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens

    @property
    def repair_calls(self) -> int:
        return sum(1 for call in self.calls if call["kind"] == "repair")

    @property
    def retry_calls(self) -> int:
        return sum(1 for call in self.calls if call["kind"] == "retry")

    @property
    def cost(self) -> float:
        return cost_cny(self.input_tokens, self.output_tokens)


class InstrumentedLLM:
    """Delegates to LLMClient while recording every Judge/repair call."""

    def __init__(
        self,
        client: LLMClient,
        recorder: CallRecorder,
        context: dict[str, str],
        *,
        metric: str,
        metric_sha: str,
    ) -> None:
        self.client = client
        self.recorder = recorder
        self.context = context
        self.metric = metric
        self.metric_sha = metric_sha

    async def chat(
        self,
        messages: Any,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: Any = None,
    ) -> Any:
        message_list = list(messages)
        system_text = "\n".join(
            str(message.get("content") or "")
            for message in message_list
            if message.get("role") == "system"
        )
        is_repair = "结构化输出修复器" in system_text
        kind = "repair" if is_repair else "primary"
        original_raw = None
        validation_error = None
        if is_repair:
            user_text = "\n".join(
                str(message.get("content") or "")
                for message in message_list
                if message.get("role") == "user"
            )
            marker = "原始输出：\n"
            if marker in user_text:
                original_raw = user_text.split(marker, 1)[1]
                if "\n\n校验错误：" in original_raw:
                    original_raw, validation_error = original_raw.split("\n\n校验错误：", 1)
                    validation_error = validation_error.split("\n\n请返回修复后的 JSON", 1)[0]
        index = self.recorder.start_call(
            case_id=self.context["case_id"],
            metric=self.metric,
            kind=kind,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_version=PROMPT_VERSION,
            prompt_sha256=self.metric_sha,
            system_head=system_text[:200],
            original_raw=original_raw,
            validation_error=validation_error,
        )
        try:
            response = await self.client.chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception as exc:  # noqa: BLE001 - record and preserve the failure
            self.recorder.finish_call(index, error=f"{type(exc).__name__}: {exc}")
            raise
        self.recorder.finish_call(
            index,
            content=response.content,
            response_model=response.model,
            usage=response.usage,
            latency_ms=response.latency_ms,
        )
        return response


def synthetic_trace(case: dict[str, Any]) -> RagTrace:
    case_id = case["id"]
    return RagTrace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"m1d4:single-case:{case_id}"),
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


def by_metric(outcomes: list[Any]) -> dict[str, Any]:
    return {outcome.metric_name: outcome for outcome in outcomes}


def validate_fingerprint(outcomes: list[Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
    }
    for outcome in outcomes:
        config = outcome.judge_config or {}
        if config.get("prompt_version") != PROMPT_VERSION:
            errors.append(f"{outcome.metric_name}: prompt_version={config.get('prompt_version')!r}")
        if config.get("schema_version") != "rag_judge_schema_v3":
            errors.append(f"{outcome.metric_name}: schema_version={config.get('schema_version')!r}")
        if config.get("metric_version") != "v3":
            errors.append(f"{outcome.metric_name}: metric_version={config.get('metric_version')!r}")
        if config.get("temperature") not in (0.0, 0):
            errors.append(f"{outcome.metric_name}: temperature={config.get('temperature')!r}")
        if config.get("max_tokens") != 8192:
            errors.append(f"{outcome.metric_name}: max_tokens={config.get('max_tokens')!r}")
        if config.get("model") not in (None, "qwen-max"):
            errors.append(f"{outcome.metric_name}: model={config.get('model')!r}")
        expected_sha = expected.get(outcome.metric_name)
        if expected_sha and config.get("prompt_sha256") != expected_sha:
            errors.append(f"{outcome.metric_name}: prompt_sha256={config.get('prompt_sha256')!r}")
    return errors


def q23_checks(f: Any, strict: Any, c: Any, r: Any) -> dict[str, Any]:
    failures: list[str] = []
    notes: list[str] = []
    if f is None or f.status != "evaluated":
        failures.append(f"Q23 F status={getattr(f, 'status', None)}")
    if c is None or c.status != "evaluated":
        failures.append(f"Q23 C status={getattr(c, 'status', None)}")
    if r is None or r.status != "evaluated":
        failures.append(f"Q23 R status={getattr(r, 'status', None)}")
    claims = list((getattr(f, "details", {}) or {}).get("claims") or [])
    absences = [claim for claim in claims if claim.get("claim_subtype") == "absence"]
    if not absences:
        failures.append("Q23 no absence claim found")
    for claim in absences:
        if claim.get("claim_type") != "non_factual":
            failures.append(f"Q23 absence {claim.get('claim_id')} type={claim.get('claim_type')}")
        if claim.get("support_status") is not None:
            failures.append(
                f"Q23 absence {claim.get('claim_id')} support_status="
                f"{claim.get('support_status')!r}"
            )
        if claim.get("evidence_refs"):
            failures.append(f"Q23 absence {claim.get('claim_id')} has evidence")
    for claim in claims:
        if claim.get("claim_type") != "factual_claim":
            continue
        if claim.get("claim_subtype") == "absence":
            failures.append(f"Q23 factual claim {claim.get('claim_id')} uses absence subtype")
        text = str(claim.get("claim") or "")
        if any(marker in text for marker in ABSENCE_MARKERS):
            failures.append(f"Q23 factual claim {claim.get('claim_id')} mixes absence: {text}")
    if strict is not None and strict.status == "evaluated":
        pass
    elif (
        strict is not None
        and strict.status == "skipped"
        and strict.skipped_reason == "no_decidable_claims"
        and f is not None
        and f.score == 0.0
        and (f.details or {}).get("all_insufficient") is True
        and (f.details or {}).get("supported_count") == 0
        and (f.details or {}).get("unsupported_count") == 0
    ):
        notes.append("Q23 F_strict skipped(no_decidable_claims) allowed by exception")
    else:
        failures.append(f"Q23 F_strict status={getattr(strict, 'status', None)}")
    target_pass = in_target(getattr(f, "score", None), [0.4, 0.5])
    if not target_pass:
        notes.append(f"Q23 F target [0.4, 0.5] miss: {getattr(f, 'score', None)}")
    return {
        "passed": not failures,
        "failures": failures,
        "notes": notes,
        "target_pass": target_pass,
        "absence_count": len(absences),
        "claims": claims,
    }


def direct_exemption_quote(quote: str) -> bool:
    text = normalized(quote)
    return (
        "质量问题" in text
        and any(marker in text for marker in EXEMPTION_MARKERS)
        and ("7天" in text or "七天" in text or "无理由" in text)
    )


def q21_checks(f: Any, contexts: list[str]) -> dict[str, Any]:
    failures: list[str] = []
    notes: list[str] = []
    if f is None or f.status != "evaluated":
        failures.append(f"Q21 F status={getattr(f, 'status', None)}")
    claims = list((getattr(f, "details", {}) or {}).get("claims") or [])
    exemption_claims = [
        claim
        for claim in claims
        if "质量问题" in normalized(claim.get("claim") or "")
        and (
            "7天" in normalized(claim.get("claim") or "")
            or "七天" in normalized(claim.get("claim") or "")
            or "限制" in normalized(claim.get("claim") or "")
        )
    ]
    if not exemption_claims:
        failures.append("Q21 no 质量问题/7 天限制 claim found")
    for claim in exemption_claims:
        claim_id = claim.get("claim_id")
        status = claim.get("support_status")
        quotes = [str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])]
        if status == "insufficient_evidence":
            notes.append(f"Q21 {claim_id} insufficient_evidence")
        elif status == "supported" and any(direct_exemption_quote(quote) for quote in quotes):
            notes.append(f"Q21 {claim_id} supported by direct exemption quote")
        else:
            failures.append(f"Q21 {claim_id} status={status!r} quotes={quotes!r}")
        if any("运费" in quote or "换货" in quote for quote in quotes):
            if not any(direct_exemption_quote(quote) for quote in quotes):
                failures.append(f"Q21 {claim_id} uses freight/exchange quote")
    for claim in claims:
        text = normalized(claim.get("claim") or "")
        if "普通商品" not in text or claim.get("support_status") != "supported":
            continue
        quotes = [str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])]
        if not any(
            "普通商品" in normalized(quote)
            and ("7天" in normalized(quote) or "无理由" in normalized(quote))
            for quote in quotes
        ):
            failures.append(f"Q21 exclusion inference {claim.get('claim_id')} marked supported")
    score = getattr(f, "score", None)
    target_pass = in_target(score, [0.6, 0.7])
    semantic_pass = not failures
    return {
        "passed": semantic_pass and target_pass,
        "semantic_pass": semantic_pass,
        "semantic_pass_target_miss": semantic_pass and not target_pass,
        "failures": failures,
        "notes": notes,
        "target_pass": target_pass,
        "f_score": score,
        "f_is_one": score == 1.0,
        "claims": claims,
        "contexts_checked": len(contexts),
    }


def q11_checks(f: Any, c: Any, r: Any, contexts: list[str]) -> dict[str, Any]:
    failures: list[str] = []
    target_failures: list[str] = []
    for name, outcome, target in (
        ("F", f, [0.6, 0.9]),
        ("C", c, [0.8, 1.0]),
        ("R", r, [0.9, 1.0]),
    ):
        if outcome is None or not in_target(getattr(outcome, "score", None), target):
            target_failures.append(
                f"Q11 {name} target {target} miss: " f"{getattr(outcome, 'score', None)}"
            )
    failures.extend(target_failures)
    if f is None or f.status != "evaluated":
        failures.append(f"Q11 F status={getattr(f, 'status', None)}")
    claims = list((getattr(f, "details", {}) or {}).get("claims") or [])
    quote_checks: list[dict[str, Any]] = []
    for claim in claims:
        for ref in claim.get("evidence_refs") or []:
            quote = str(ref.get("quote") or "")
            found = any(quote and quote in context for context in contexts)
            quote_checks.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "quote": quote,
                    "contiguous_substring": found,
                }
            )
            if not found:
                failures.append(f"Q11 quote not contiguous: {quote!r}")
    return {
        "passed": not failures,
        "failures": failures,
        "target_pass": not target_failures,
        "quote_checks": quote_checks,
        "claims": claims,
    }


def call_summary(recorder: CallRecorder) -> dict[str, Any]:
    return {
        "judge_calls": recorder.judge_calls,
        "primary_calls": sum(1 for call in recorder.calls if call["kind"] == "primary"),
        "repair_calls": recorder.repair_calls,
        "retry_calls": recorder.retry_calls,
        "input_tokens": recorder.input_tokens,
        "output_tokens": recorder.output_tokens,
        "cost_cny": round(recorder.cost, 8),
        "max_judge_calls": MAX_JUDGE_CALLS,
        "ceiling_cny": CEILING_CNY,
    }


def git_check() -> dict[str, Any]:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(BASE), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    head = run("rev-parse", "HEAD")
    agent_diff = run(
        "diff", "--quiet", EXPECTED_AGENT_COMMIT, "--", "backend/app/agents/rag_judge_agent.py"
    )
    freeze_present = run("cat-file", "-e", f"{EXPECTED_FREEZE_COMMIT}^{{commit}}")
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "agent_commit": EXPECTED_AGENT_COMMIT,
        "agent_file_unchanged_since_agent_commit": agent_diff.returncode == 0,
        "freeze_commit_present": freeze_present.returncode == 0,
        "errors": []
        if head.returncode == 0 and agent_diff.returncode == 0 and freeze_present.returncode == 0
        else [
            f"git head={head.returncode}",
            f"agent_diff={agent_diff.returncode}: {agent_diff.stderr.strip()}",
            f"freeze_commit={freeze_present.returncode}",
        ],
    }


async def preflight() -> dict[str, Any]:
    application = load_json(APPLICATION_FILE)
    target = load_json(TARGET_FILE)
    labels = load_json(LABELS_FILE)
    manifest = load_json(MANIFEST_FILE)
    validation = load_json(VALIDATION_FILE)
    application_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    target_sha = sha256_bytes(TARGET_FILE.read_bytes())
    labels_sha = sha256_bytes(LABELS_FILE.read_bytes())
    manifest_sha = sha256_bytes(MANIFEST_FILE.read_bytes())
    validation_sha = sha256_bytes(VALIDATION_FILE.read_bytes())
    prompt_sha = {
        name: sha256_bytes((PROMPT_DIR / name).read_bytes()) for name in EXPECTED_PROMPT_SHA
    }
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=PROMPT_VERSION)
    repair_text = agent._repair_example() or ""
    repair_sha = sha256_text(repair_text)
    git = git_check()
    errors: list[str] = []
    if application_sha != EXPECTED_APPLICATION_SHA:
        errors.append(f"application_sha={application_sha}")
    if fixture_sha != EXPECTED_FIXTURE_SHA:
        errors.append(f"fixture_sha={fixture_sha}")
    if target_sha != EXPECTED_TARGET_SHA:
        errors.append(f"target_sha={target_sha}")
    if labels_sha != EXPECTED_LABELS_SHA:
        errors.append(f"labels_sha={labels_sha}")
    if manifest_sha != EXPECTED_MANIFEST_SHA:
        errors.append(f"manifest_sha={manifest_sha}")
    if validation_sha != EXPECTED_VALIDATION_SHA:
        errors.append(f"validation_sha={validation_sha}")
    if prompt_sha != EXPECTED_PROMPT_SHA:
        errors.append(f"prompt_sha={prompt_sha}")
    if repair_sha != EXPECTED_REPAIR_SHA:
        errors.append(f"repair_sha={repair_sha}")
    if application.get("meta", {}).get("status") != "pending_approval":
        errors.append("application status is not pending_approval")
    if manifest.get("status") != "frozen" or manifest.get("active") is not False:
        errors.append("manifest is not frozen/inactive")
    if manifest.get("default_prompt_version") != "v1.0.0":
        errors.append("manifest default_prompt_version is not v1.0.0")
    if validation.get("status") != "pass":
        errors.append("prompt validation is not pass")
    if settings.DEFAULT_LLM_MODEL != "qwen-max":
        errors.append(f"model={settings.DEFAULT_LLM_MODEL!r}")
    if settings.DEFAULT_TEMPERATURE != 0.0:
        errors.append(f"temperature={settings.DEFAULT_TEMPERATURE!r}")
    if settings.RAG_JUDGE_MAX_TOKENS != 8192:
        errors.append(f"max_tokens={settings.RAG_JUDGE_MAX_TOKENS!r}")
    if settings.RAG_JUDGE_PROMPT_VERSION != "v1.0.0":
        errors.append(f"default_prompt_version={settings.RAG_JUDGE_PROMPT_VERSION!r}")
    errors.extend(git["errors"])

    preflight_usage = {"input": 0, "output": 0}
    preflight_error = None
    if not errors:
        try:
            async with LLMClient() as llm:
                response = await llm.chat(
                    [{"role": "user", "content": "ping"}],
                    max_tokens=8,
                )
                preflight_usage = {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                }
        except Exception as exc:  # noqa: BLE001 - preflight reports credential/endpoint issues
            preflight_error = f"{type(exc).__name__}: {exc}"
            errors.append(f"llm_ping={preflight_error}")

    return {
        "application_sha256": application_sha,
        "fixture_sha256": fixture_sha,
        "target_sha256": target_sha,
        "labels_sha256": labels_sha,
        "manifest_sha256": manifest_sha,
        "validation_sha256": validation_sha,
        "prompt_sha256": prompt_sha,
        "repair_example_sha256": repair_sha,
        "repair_example_version": PROMPT_VERSION,
        "agent_commit": git["agent_commit"],
        "agent_file_unchanged_since_agent_commit": git["agent_file_unchanged_since_agent_commit"],
        "freeze_commit": EXPECTED_FREEZE_COMMIT,
        "freeze_commit_present": git["freeze_commit_present"],
        "git_head": git["head"],
        "prompt_version": PROMPT_VERSION,
        "prompt_status": manifest.get("status"),
        "active": manifest.get("active"),
        "default_prompt_version": settings.RAG_JUDGE_PROMPT_VERSION,
        "schema_version": manifest.get("schema_version"),
        "rubric_version": manifest.get("rubric_version"),
        "metric_version": "v3",
        "model": settings.DEFAULT_LLM_MODEL,
        "temperature": settings.DEFAULT_TEMPERATURE,
        "max_tokens": settings.RAG_JUDGE_MAX_TOKENS,
        "preflight_usage": preflight_usage,
        "preflight_error": preflight_error,
        "errors": errors,
        "application": application,
        "target": target,
        "labels": labels,
        "manifest": manifest,
        "validation": validation,
    }


def render_case_table(case: dict[str, Any]) -> list[str]:
    lines = [
        f"### {case['case_id']} — {case['status']}",
        "",
        f"- targets：`{case['targets']}`",
        f"- checks：`{json.dumps(case['checks'], ensure_ascii=False)}`",
        "",
        "| metric | status | score | skipped/invalid |",
        "|---|---|---:|---|",
    ]
    for name, payload in case["metrics"].items():
        lines.append(
            f"| {name} | {payload['status']} | {payload.get('score')} | "
            f"{payload.get('skipped_reason') or payload.get('invalid_reason') or '—'} |"
        )
    lines.append("")
    claims = case.get("claims") or []
    if claims:
        lines.extend(
            [
                "| claim_id | claim | type | subtype | support | evidence quotes |",
                "|---|---|---|---|---|---|",
            ]
        )
        for claim in claims:
            quotes = [str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])]
            lines.append(
                f"| {claim.get('claim_id')} | {claim.get('claim')} | "
                f"{claim.get('claim_type')} | {claim.get('claim_subtype')} | "
                f"{claim.get('support_status')} | {json.dumps(quotes, ensure_ascii=False)} |"
            )
        lines.append("")
    return lines


async def main() -> None:
    preflight_result = await preflight()
    print(
        json.dumps(
            {
                "runtime_fingerprint": {
                    key: value
                    for key, value in preflight_result.items()
                    if key
                    not in {
                        "application",
                        "target",
                        "labels",
                        "manifest",
                        "validation",
                    }
                }
            },
            ensure_ascii=False,
            indent=1,
        ),
        flush=True,
    )
    application = preflight_result["application"]
    fixture = load_json(FIXTURE_FILE)
    by_id = {case["id"]: case for case in fixture["cases"]}
    app_by_id = {case["case_id"]: case for case in application["cases"]}
    recorder = CallRecorder()
    context = {"case_id": ""}
    effective: list[dict[str, Any]] = []

    results: dict[str, Any] = {
        "meta": {
            "name": "m1d4-v1.2.2-single-case-diagnostic-results",
            "kind": "judge_only_production_service_replay_not_end_to_end",
            "date": "2026-11-22",
            "diagnostic_only": True,
            "application_sha256": preflight_result["application_sha256"],
            "judge_run": True,
            "created_run": False,
            "wrote_db": False,
            "runtime_activated": False,
            "default_prompt_version": preflight_result["default_prompt_version"],
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": preflight_result["prompt_sha256"],
            "manifest_sha256": preflight_result["manifest_sha256"],
            "validation_sha256": preflight_result["validation_sha256"],
            "fixture_sha256": preflight_result["fixture_sha256"],
            "target_sha256": preflight_result["target_sha256"],
            "labels_sha256": preflight_result["labels_sha256"],
            "repair_example_sha256": preflight_result["repair_example_sha256"],
            "agent_commit": preflight_result["agent_commit"],
            "freeze_commit": preflight_result["freeze_commit"],
            "git_head": preflight_result["git_head"],
            "preflight": {
                key: value
                for key, value in preflight_result.items()
                if key
                not in {
                    "application",
                    "target",
                    "labels",
                    "manifest",
                    "validation",
                }
            },
        },
        "effective_prompt_versions": effective,
        "cases": [],
        "calls": recorder.calls,
        "stop_triggered": False,
        "stop_reason": None,
        "gate": {
            "passed": False,
            "verified": False,
            "semantic_pass_target_miss": False,
            "failures": [],
            "notes": [],
        },
    }

    if preflight_result["errors"]:
        results["stop_triggered"] = True
        results["stop_reason"] = "preflight: " + "; ".join(preflight_result["errors"])
    else:
        async with LLMClient() as real_llm:

            def factory(metric: str) -> RagJudgeAgent:
                loaded = load_judge_prompt(PROMPT_VERSION, metric)
                loaded_sha = sha256_text(loaded)
                effective.append(
                    {
                        "case_id": context["case_id"],
                        "metric": metric,
                        "prompt_version": PROMPT_VERSION,
                        "prompt_sha256": loaded_sha,
                        "f_sha256": EXPECTED_PROMPT_SHA["faithfulness.txt"],
                        "schema_version": "rag_judge_schema_v3",
                        "metric_version": "v3",
                    }
                )
                print(
                    json.dumps(
                        {
                            "effective_prompt_version": PROMPT_VERSION,
                            "case_id": context["case_id"],
                            "metric": metric,
                            "prompt_sha256": loaded_sha,
                            "f_sha256": EXPECTED_PROMPT_SHA["faithfulness.txt"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                return RagJudgeAgent(
                    metric,
                    prompt_version=PROMPT_VERSION,
                    llm=InstrumentedLLM(
                        real_llm,
                        recorder,
                        context,
                        metric=metric,
                        metric_sha=loaded_sha,
                    ),
                )

            for case_id in CASE_IDS:
                source = by_id[case_id]
                context["case_id"] = case_id
                app_case = app_by_id[case_id]
                print(
                    json.dumps(
                        {
                            "starting_case": case_id,
                            "prompt_version": PROMPT_VERSION,
                            "f_sha256": EXPECTED_PROMPT_SHA["faithfulness.txt"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                outcomes = await judge_trace(
                    session=None,
                    trace=synthetic_trace(source),
                    item=SimpleNamespace(gold_answer=source["gold_answer"]),
                    prompt_version=PROMPT_VERSION,
                    agent_factory=factory,
                )
                outcomes_by_name = by_metric(outcomes)
                fingerprint_errors = validate_fingerprint(outcomes)
                f = outcomes_by_name.get("faithfulness")
                strict = outcomes_by_name.get("faithfulness_strict")
                c = outcomes_by_name.get("answer_correctness")
                r = outcomes_by_name.get("answer_relevancy")
                contexts = [ctx["content"] for ctx in source["contexts"]]
                case_result: dict[str, Any] = {
                    "case_id": case_id,
                    "group": app_case["group"],
                    "final_category": app_case["final_category"],
                    "targets": app_case["targets"],
                    "metrics": {
                        name: {
                            "status": outcome.status,
                            "score": outcome.score,
                            "skipped_reason": outcome.skipped_reason,
                            "invalid_reason": outcome.invalid_reason,
                        }
                        for name, outcome in outcomes_by_name.items()
                    },
                    "fingerprint_errors": fingerprint_errors,
                    "outcomes": [outcome_payload(outcome) for outcome in outcomes],
                    "claims": [],
                }

                if fingerprint_errors:
                    results["stop_triggered"] = True
                    results["stop_reason"] = f"{case_id}: fingerprint: " + "; ".join(
                        fingerprint_errors
                    )
                    case_result["status"] = "stopped"
                    case_result["checks"] = {
                        "passed": False,
                        "failures": fingerprint_errors,
                        "notes": [],
                    }
                elif any(outcome.status in {"invalid", "failed"} for outcome in outcomes):
                    bad = [
                        f"{outcome.metric_name}={outcome.status}"
                        f"({outcome.invalid_reason or outcome.error_type})"
                        for outcome in outcomes
                        if outcome.status in {"invalid", "failed"}
                    ]
                    results["stop_triggered"] = True
                    results["stop_reason"] = f"{case_id}: " + ", ".join(bad)
                    case_result["status"] = "stopped"
                    case_result["checks"] = {
                        "passed": False,
                        "failures": bad,
                        "notes": [],
                    }
                elif case_id == "Q23":
                    checks = q23_checks(f, strict, c, r)
                    case_result["checks"] = checks
                    case_result["claims"] = checks.pop("claims")
                    case_result["status"] = "passed" if checks["passed"] else "failed"
                    if not checks["passed"]:
                        results["stop_triggered"] = True
                        results["stop_reason"] = "Q23 contract: " + "; ".join(checks["failures"])
                elif case_id == "Q21":
                    checks = q21_checks(f, contexts)
                    case_result["checks"] = checks
                    case_result["claims"] = checks.pop("claims")
                    if checks["semantic_pass_target_miss"]:
                        case_result["status"] = "semantic_pass_target_miss"
                        results["stop_triggered"] = True
                        results["stop_reason"] = (
                            "Q21 semantic_pass_target_miss: "
                            f"F={checks['f_score']} target=[0.6, 0.7]"
                        )
                        results["gate"]["semantic_pass_target_miss"] = True
                    elif checks["passed"]:
                        case_result["status"] = "passed"
                    else:
                        case_result["status"] = "failed"
                        results["stop_triggered"] = True
                        results["stop_reason"] = "Q21 semantic: " + "; ".join(checks["failures"])
                else:
                    checks = q11_checks(f, c, r, contexts)
                    case_result["checks"] = checks
                    case_result["claims"] = checks.pop("claims")
                    case_result["status"] = "passed" if checks["passed"] else "failed"
                    if not checks["passed"]:
                        results["stop_triggered"] = True
                        results["stop_reason"] = "Q11 regression: " + "; ".join(checks["failures"])

                results["cases"].append(case_result)
                print(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "status": case_result["status"],
                            "metrics": case_result["metrics"],
                            "judge_calls": recorder.judge_calls,
                            "cost_cny": round(recorder.cost, 8),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

                if recorder.judge_calls > MAX_JUDGE_CALLS or recorder.cost > CEILING_CNY:
                    results["stop_triggered"] = True
                    results["stop_reason"] = (
                        f"budget: calls={recorder.judge_calls}, " f"cost={recorder.cost:.6f}"
                    )
                if results["stop_triggered"]:
                    break

    completed = {case["case_id"] for case in results["cases"]}
    failures: list[str] = []
    notes: list[str] = []
    for case in results["cases"]:
        checks = case.get("checks") or {}
        failures.extend(checks.get("failures") or [])
        notes.extend(checks.get("notes") or [])
    if not results["stop_triggered"]:
        if completed != set(CASE_IDS):
            failures.append(f"unprocessed cases: {sorted(set(CASE_IDS) - completed)}")
        for case_id in CASE_IDS:
            case = next(
                (item for item in results["cases"] if item["case_id"] == case_id),
                None,
            )
            if case is None or case["status"] != "passed":
                failures.append(
                    f"{case_id} status={getattr(case, 'get', lambda *_: None)('status')}"
                )
    results["gate"] = {
        "passed": not failures and not results["stop_triggered"],
        "verified": not failures and not results["stop_triggered"],
        "semantic_pass_target_miss": results["gate"]["semantic_pass_target_miss"],
        "failures": failures,
        "notes": notes,
    }
    if results["gate"]["semantic_pass_target_miss"]:
        results["meta"]["status"] = "semantic_pass_target_miss"
    elif results["stop_triggered"]:
        results["meta"]["status"] = "stopped"
    elif results["gate"]["passed"]:
        results["meta"]["status"] = "passed"
    else:
        results["meta"]["status"] = "failed"
    results["meta"]["verified"] = results["meta"]["status"] == "passed"
    results["meta"]["diagnostic_only"] = True
    results["meta"]["totals"] = call_summary(recorder)
    results["meta"]["preflight_usage"] = preflight_result["preflight_usage"]
    results["meta"]["preflight_cost_cny"] = round(
        cost_cny(
            preflight_result["preflight_usage"]["input"],
            preflight_result["preflight_usage"]["output"],
        ),
        8,
    )
    results["calls"] = recorder.calls

    OUT_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    json_sha = sha256_bytes(OUT_JSON.read_bytes())
    OUT_SHA.write_text(
        f"{json_sha}  {OUT_JSON.name}\n",
        encoding="utf-8",
        newline="\n",
    )

    primary_calls = recorder.judge_calls - recorder.repair_calls - recorder.retry_calls
    lines = [
        "# M1-D-4 v1.2.2 单案例诊断结果（Q23 / Q21 / Q11）",
        "",
        f"> 状态：`{results['meta']['status']}`；diagnostic only；未创建 Run、未写 DB、未激活 v1.2.2。",
        f"> application SHA：`{preflight_result['application_sha256']}`",
        f"> 结果 JSON SHA：`{json_sha}`",
        f"> Prompt：`v1.2.2` / `frozen` / F `{EXPECTED_PROMPT_SHA['faithfulness.txt']}`",
        f"> MANIFEST：`{preflight_result['manifest_sha256']}`；"
        f"validation：`{preflight_result['validation_sha256']}`",
        f"> fixture：`{preflight_result['fixture_sha256']}`；"
        f"target：`{preflight_result['target_sha256']}`；"
        f"labels：`{preflight_result['labels_sha256']}`",
        f"> agent_commit：`{preflight_result['agent_commit']}`；"
        f"repair SHA：`{preflight_result['repair_example_sha256']}`",
        f"> git HEAD：`{preflight_result['git_head']}`",
        "",
        "## 1. 运行时指纹",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 生效 Prompt 版本 | `{PROMPT_VERSION}`" "（显式传参；默认仍 `v1.0.0`） |",
        f"| F SHA | `{EXPECTED_PROMPT_SHA['faithfulness.txt']}` |",
        f"| C SHA | `{EXPECTED_PROMPT_SHA['answer_correctness.txt']}` |",
        f"| R SHA | `{EXPECTED_PROMPT_SHA['answer_relevancy.txt']}` |",
        f"| MANIFEST / validation | `{preflight_result['manifest_sha256']}` / "
        f"`{preflight_result['validation_sha256']}` |",
        f"| fixture / target / labels | `{preflight_result['fixture_sha256']}` / "
        f"`{preflight_result['target_sha256']}` / "
        f"`{preflight_result['labels_sha256']}` |",
        f"| agent_commit / repair SHA | `{preflight_result['agent_commit']}` / "
        f"`{preflight_result['repair_example_sha256']}` |",
        f"| prompt_status / active | `{preflight_result['prompt_status']}` / "
        f"`{preflight_result['active']}` |",
        f"| model | `{preflight_result['model']}` |",
        f"| temperature / max_tokens | `{preflight_result['temperature']}` / "
        f"`{preflight_result['max_tokens']}` |",
        f"| 默认版本 | `{preflight_result['default_prompt_version']}` |",
        f"| 运行时指纹错误 | `{preflight_result['errors'] or '—'}` |",
        "",
        "## 2. 三案例结果",
        "",
        "| Case | F | F_strict | C | R | target | status |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for case in results["cases"]:
        metrics = case["metrics"]
        f = metrics.get("faithfulness", {})
        fs = metrics.get("faithfulness_strict", {})
        c = metrics.get("answer_correctness", {})
        r = metrics.get("answer_relevancy", {})
        checks = case.get("checks") or {}
        target = "pass" if checks.get("target_pass") is not False else "miss"
        lines.append(
            f"| {case['case_id']} | {f.get('score', f.get('status'))} | "
            f"{fs.get('score', fs.get('status'))} | {c.get('score', c.get('status'))} | "
            f"{r.get('score', r.get('status'))} | {target} | {case['status']} |"
        )
    lines.extend(["", "## 3. 逐案例明细", ""])
    for case in results["cases"]:
        lines.extend(render_case_table(case))
    lines.extend(
        [
            "## 4. 调用与成本",
            "",
            "| 项 | 实际 | 预算/上限 |",
            "|---|---:|---:|",
            f"| Judge calls | {recorder.judge_calls} | {MAX_JUDGE_CALLS} |",
            f"| primary | {primary_calls} | 9 |",
            f"| repair | {recorder.repair_calls} | 3 |",
            f"| retry | {recorder.retry_calls} | 2 |",
            f"| input tokens | {recorder.input_tokens} | — |",
            f"| output tokens | {recorder.output_tokens} | — |",
            f"| Judge cost CNY | {recorder.cost:.6f} | {CEILING_CNY:.2f} |",
            f"| preflight tokens | {preflight_result['preflight_usage']['input']} / "
            f"{preflight_result['preflight_usage']['output']} | — |",
            f"| preflight cost CNY | " f"{results['meta']['preflight_cost_cny']:.6f} | — |",
            "",
            "## 5. 停止与门禁",
            "",
            f"- stop_triggered：`{results['stop_triggered']}`",
            f"- stop_reason：{results['stop_reason'] or '—'}",
            f"- gate passed：`{results['gate']['passed']}`",
            f"- gate verified：`{results['gate']['verified']}`",
            f"- semantic_pass_target_miss：" f"`{results['gate']['semantic_pass_target_miss']}`",
            f"- gate failures：{results['gate']['failures'] or '—'}",
            f"- gate notes：{results['gate']['notes'] or '—'}",
            "",
            "## 6. 交付声明",
            "",
            "- diagnostic only；不是 10 条，也不是 40 条；不计入 10 条样本。",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora/RAG adapter。",
            "- 未激活 v1.2.2；active/runtime_active 保持 false；默认仍 `v1.0.0`。",
            "- 未跑 10/40；单案例通过后才可重新提交 10 条申请。",
            "- 结论只使用 implemented / verified / blocked；未写 accepted。",
            "",
            "## 7. Repair 轮摘要",
            "",
            "| # | case | metric | original chars | repaired chars |",
            "|---|---|---|---:|---:|",
        ]
    )
    for call in recorder.calls:
        if call["kind"] != "repair":
            continue
        lines.append(
            f"| {call['call_index']} | {call['case_id']} | {call['metric']} | "
            f"{len(call.get('original_raw') or '')} | {len(call.get('content') or '')} |"
        )
    if recorder.repair_calls == 0:
        lines.append("| — | — | — | 0 | 0 |")
    lines.extend(
        [
            "",
            "## 8. 原始输出",
            "",
            "完整原始输出、repair 前后文本、usage 见 `m1d4-single-case-results.json`；以下为最终输出。",
            "",
        ]
    )
    for case in results["cases"]:
        for outcome in case["outcomes"]:
            if outcome["metric_name"] == "faithfulness_strict":
                continue
            lines.extend(
                [
                    f"### {case['case_id']} / {outcome['metric_name']}",
                    "",
                    "```text",
                    str(outcome.get("raw_output") or ""),
                    "```",
                    "",
                ]
            )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    md_sha = sha256_bytes(OUT_MD.read_bytes())
    print(
        json.dumps(
            {
                "status": results["meta"]["status"],
                "verified": results["meta"]["verified"],
                "stop_triggered": results["stop_triggered"],
                "stop_reason": results["stop_reason"],
                "gate": results["gate"],
                "totals": results["meta"]["totals"],
                "json_sha256": json_sha,
                "md_sha256": md_sha,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    import sys

    if "--preflight-only" in sys.argv:
        result = asyncio.run(preflight())
        print(
            json.dumps(
                {
                    key: value
                    for key, value in result.items()
                    if key
                    not in {
                        "application",
                        "target",
                        "labels",
                        "manifest",
                        "validation",
                    }
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        raise SystemExit(1 if result["errors"] else 0)
    asyncio.run(main())
