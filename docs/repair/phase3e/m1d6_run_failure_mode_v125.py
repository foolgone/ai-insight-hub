"""M1-D-6 v1.2.5 failure-mode diagnostic runner (10 cases x 1 run).

- 10 cases x 1 run x 3 metrics = 30 primary; 10 F patch + 3 retry reserve.
- max 43 calls / CNY 0.80.
- judge_trace(session=None); no Run/DB/WeKnora/RAG adapter.
- diagnostic_only: invalid continues; no HG repeats; no PASS.
- append-only ledger at the LLM boundary.

Dry-run (no LLM):
    python docs/repair/phase3e/m1d6_run_failure_mode_v125.py --dry-run
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BASE = Path(__file__).resolve().parents[3]
if str(BASE / "backend") not in sys.path:
    sys.path.insert(0, str(BASE / "backend"))

if not os.environ.get("DASHSCOPE_API_KEY"):
    raise SystemExit("DASHSCOPE_API_KEY is required for the approved qwen-max run")
os.environ["DEEPSEEK_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
os.environ["DEEPSEEK_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
os.environ["DEFAULT_LLM_MODEL"] = "qwen-max"
os.environ["DEFAULT_TEMPERATURE"] = "0.0"
os.environ["RAG_JUDGE_MAX_TOKENS"] = "8192"

from app.agents.rag_judge_agent import (  # noqa: E402
    RagJudgeAgent,
    load_judge_prompt,
)
from app.agents.structured_output import extract_json_text  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.llm import LLMClient  # noqa: E402
from app.models.rag import RagTrace  # noqa: E402
from app.schemas.agents.rag_judge_evidence import quote_validator_sha256  # noqa: E402
from app.services.rag_judge_service import judge_trace  # noqa: E402

APPLICATION_FILE = BASE / "docs/repair/phase3e/m1d6-v125-failure-mode-application.json"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.5/MANIFEST.json"
VALIDATION_FILE = BASE / "docs/repair/phase3e/m1d7-prompt-v1.2.5-validation.json"
LEAKAGE_AUDIT_FILE = BASE / "docs/repair/phase3e/m1d7-prompt-leakage-audit.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.5"
PATCH_SCHEMA_FILE = BASE / "backend/app/schemas/agents/rag_judge_patch_v125.py"
LEDGER_FILE = BASE / "docs/repair/phase3e/m1d6-v125-failure-mode-ledger.jsonl"
OUT_JSON = BASE / "docs/repair/phase3e/m1d6-v125-failure-mode-results.json"
OUT_MD = BASE / "docs/repair/58-m1d6-v1.2.5-failure-mode-diagnostic-results.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d6-v125-failure-mode-results.sha256"
OUT_REPORT_SHA = BASE / "docs/repair/phase3e/m1d6-v125-failure-mode-report.sha256"

EXPECTED_APPLICATION_SHA = (
    "148118fe94570d44948113895ed38617ba3ca962252edd74de704a44a30ebe08"
)
EXPECTED_FIXTURE_SHA = (
    "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"
)
EXPECTED_TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
EXPECTED_LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
EXPECTED_MANIFEST_SHA = (
    "2e4ef8bf93f4a6f39a96eeee49e75b4939ca8e3242e12f3028c9b3d8733930c1"
)
EXPECTED_VALIDATION_SHA = (
    "20ab5ca34ad408ed2fc90b6f77b7bab04c39ea02ed5539300c9a3c027ab81998"
)
EXPECTED_LEAKAGE_AUDIT_SHA = (
    "28937947e07d2169b6336b2762a51f958518f0f27d18ae1867b97ef6a715a904"
)
EXPECTED_PATCH_SCHEMA_SHA = (
    "bfc71529c4ef057dec7256c35ad31341cc31924f5a2784469721323f74547f33"
)
EXPECTED_PATCH_EXAMPLE_SHA = (
    "43f48a420ead52cb21f0472a89040de4ef0480cebbe476a104a0edcbc0d62a6d"
)
EXPECTED_QUOTE_VALIDATOR_SHA = (
    "153ab4a6f203ca0398133a2cc2ca6fda834f7670afa90651c66cfa44b92c722a"
)
EXPECTED_LEDGER_INITIAL_SHA = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
EXPECTED_FREEZE_COMMIT = "e9e5f8e"
EXPECTED_AGENT_COMMIT = "318b302"
EXPECTED_TEST_FIX_COMMIT = "e690b00"
EXPECTED_IMPLEMENTATION_REPORT_COMMIT = "e22eb04"
EXPECTED_DESIGN_COMMIT = "c09cf15"
EXPECTED_PROMPT_SHA = {
    "faithfulness.txt": "9c80d4d5cd60ea7c95ad02c71f97ab566cc2fd82e2a2230124ee4b21247b9d8e",
    "answer_correctness.txt": "ca489fcf39691e9a71aec004a01938fb6c70b7b17da3c55fb0ada066e1d24968",
    "answer_relevancy.txt": "f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc",
}

PROMPT_VERSION = "v1.2.5"
RUBRIC_VERSION = "v1.2.0"
SCHEMA_VERSION = "rag_judge_schema_v3"
METRIC_VERSION = "v3"
DEFAULT_PROMPT_VERSION = "v1.0.0"
MAX_JUDGE_CALLS = 43
CEILING_CNY = 0.80
CASE_IDS = (
    "Q01",
    "Q04",
    "Q11",
    "Q17",
    "Q21",
    "Q23",
    "Q29",
    "Q31",
    "Q35",
    "Q36",
)
PRICE_INPUT = 0.0024 / 1000
PRICE_OUTPUT = 0.0096 / 1000
FIXED_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "m1d6:v125:failure-mode:user")
EXEMPTION_MARKERS = ("不受", "不适用", "除外", "例外", "仍可", "可以申请")
SPECIFIC_GOODS_MARKERS = ("定制", "生鲜", "虚拟")


class LedgerError(RuntimeError):
    """Ledger integrity failure."""


class BudgetExceeded(RuntimeError):
    """Raised before a call that would exceed the approved budget."""


@dataclass
class LedgerWriter:
    path: Path
    expected_initial_sha256: str
    require_empty: bool = True
    _seq: int = 0
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    _open: dict[int, dict[str, Any]] = field(default_factory=dict)
    entries: list[dict[str, Any]] = field(default_factory=list)
    budget_error: str | None = None
    initial_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.path.exists():
            self.path.write_bytes(b"")
        data = self.path.read_bytes()
        self.initial_sha256 = sha256_bytes(data)
        if self.initial_sha256 != self.expected_initial_sha256:
            raise LedgerError(
                "ledger initial SHA mismatch: "
                f"{self.initial_sha256} != {self.expected_initial_sha256}"
            )
        if self.require_empty and data:
            raise LedgerError("ledger is not empty at run start")

    def _append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self.entries.append(record)

    def start(self, **fields: Any) -> int:
        if self.attempts >= MAX_JUDGE_CALLS:
            self.budget_error = f"attempts {self.attempts} >= {MAX_JUDGE_CALLS}"
            raise BudgetExceeded(self.budget_error)
        if self.cost > CEILING_CNY:
            self.budget_error = f"cost {self.cost:.6f} > {CEILING_CNY:.2f}"
            raise BudgetExceeded(self.budget_error)
        self._seq += 1
        seq = self._seq
        record = {
            "event": "started",
            "seq": seq,
            "call_id": f"call-{seq:03d}",
            "timestamp": utc_now(),
            **fields,
        }
        self._append(record)
        self.attempts += 1
        self._open[seq] = record
        return seq

    def finish(
        self,
        seq: int,
        *,
        status: str,
        response_model: str | None,
        usage: Any,
        latency_ms: float | None,
        content: str | None,
        error: str | None,
    ) -> None:
        started = self._open.pop(seq, None)
        if started is None:
            raise LedgerError(f"finished without started seq={seq}")
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        cost = cost_cny(input_tokens, output_tokens)
        record = {
            "event": "finished",
            "seq": seq,
            "call_id": started.get("call_id"),
            "timestamp": utc_now(),
            "status": status,
            "response_model": response_model,
            "usage": {"input": input_tokens, "output": output_tokens},
            "cost_cny": round(cost, 8),
            "latency_ms": round(float(latency_ms), 3)
            if latency_ms is not None
            else None,
            "content_chars": len(content or ""),
            "content_sha256": sha256_text(content or ""),
            "error": error,
        }
        self._append(record)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if self.cost > CEILING_CNY:
            self.budget_error = f"cost {self.cost:.6f} > {CEILING_CNY:.2f}"

    @property
    def cost(self) -> float:
        return cost_cny(self.input_tokens, self.output_tokens)

    @property
    def uncertain_calls(self) -> int:
        return len(self._open)

    @property
    def finished_calls(self) -> int:
        return self.attempts - len(self._open)

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.path.read_bytes())

    def summary(self) -> dict[str, Any]:
        started = [r for r in self.entries if r.get("event") == "started"]
        finished = {
            int(r["seq"]): r for r in self.entries if r.get("event") == "finished"
        }
        rows: list[dict[str, Any]] = []
        for record in started:
            seq = int(record["seq"])
            fin = finished.get(seq) or {}
            usage = fin.get("usage") or {}
            rows.append(
                {
                    "seq": seq,
                    "call_id": record.get("call_id"),
                    "case_id": record.get("case_id"),
                    "run_id": record.get("run_id"),
                    "metric": record.get("metric"),
                    "kind": record.get("kind"),
                    "status": fin.get("status"),
                    "input_tokens": int(usage.get("input") or 0),
                    "output_tokens": int(usage.get("output") or 0),
                    "cost_cny": float(fin.get("cost_cny") or 0.0),
                    "error": fin.get("error"),
                }
            )
        return {
            "file": str(self.path.relative_to(BASE)),
            "sha256": self.sha256,
            "initial_sha256": self.initial_sha256,
            "total_attempts": self.attempts,
            "finished_calls": self.finished_calls,
            "uncertain_calls": self.uncertain_calls,
            "started_by_kind": dict(
                Counter(str(r.get("kind") or "primary") for r in started)
            ),
            "started_by_case": dict(
                Counter(str(r.get("case_id") or "?") for r in started)
            ),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_cny": round(self.cost, 8),
            "ceiling_cny": CEILING_CNY,
            "max_judge_calls": MAX_JUDGE_CALLS,
            "budget_error": self.budget_error,
            "rows": rows,
        }


@dataclass
class CallRecorder:
    ledger: LedgerWriter
    calls: list[dict[str, Any]] = field(default_factory=list)
    budget_exceeded: bool = False

    def start_call(
        self,
        *,
        case_id: str,
        run_id: str,
        metric: str,
        kind: str,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        prompt_version: str,
        prompt_sha256: str,
        system_prompt_sha256: str,
        system_head: str,
        original_raw: str | None = None,
        validation_error: str | None = None,
        patch_claim_ids: list[str] | None = None,
    ) -> int:
        try:
            seq = self.ledger.start(
                case_id=case_id,
                run_id=run_id,
                metric=metric,
                kind=kind,
                model_requested=model,
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_version=prompt_version,
                prompt_sha256=prompt_sha256,
                system_prompt_sha256=system_prompt_sha256,
                system_head=system_head,
                patch_claim_ids=list(patch_claim_ids or []),
                validation_error=validation_error,
            )
        except BudgetExceeded:
            self.budget_exceeded = True
            raise
        index = len(self.calls)
        self.calls.append(
            {
                "call_index": seq,
                "ledger_seq": seq,
                "case_id": case_id,
                "run_id": run_id,
                "metric": metric,
                "kind": kind,
                "model_requested": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "prompt_version": prompt_version,
                "prompt_sha256": prompt_sha256,
                "system_prompt_sha256": system_prompt_sha256,
                "system_head": system_head,
                "original_raw": original_raw,
                "validation_error": validation_error,
                "patch_claim_ids": list(patch_claim_ids or []),
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
        status = "error" if error else "ok"
        self.ledger.finish(
            int(record["ledger_seq"]),
            status=status,
            response_model=response_model,
            usage=usage,
            latency_ms=latency_ms,
            content=content,
            error=error,
        )
        record["content"] = content
        record["response_model"] = response_model
        record["latency_ms"] = latency_ms
        record["error"] = error
        if usage is not None:
            record["usage"] = {
                "input": int(getattr(usage, "input_tokens", 0) or 0),
                "output": int(getattr(usage, "output_tokens", 0) or 0),
            }
        if self.ledger.budget_error:
            self.budget_exceeded = True

    @property
    def judge_calls(self) -> int:
        return self.ledger.attempts

    @property
    def cost(self) -> float:
        return self.ledger.cost

    def for_case(self, case_id: str) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["case_id"] == case_id]

    def summary_for_case(self, case_id: str) -> dict[str, Any]:
        calls = self.for_case(case_id)
        input_tokens = sum(
            int((call.get("usage") or {}).get("input") or 0) for call in calls
        )
        output_tokens = sum(
            int((call.get("usage") or {}).get("output") or 0) for call in calls
        )
        return {
            "calls": len(calls),
            "primary": sum(1 for call in calls if call["kind"] == "primary"),
            "patch": sum(1 for call in calls if call["kind"] == "patch"),
            "repair": sum(1 for call in calls if call["kind"] == "repair"),
            "retry": sum(1 for call in calls if call["kind"] == "retry"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_cny": round(cost_cny(input_tokens, output_tokens), 8),
        }


class InstrumentedLLM:
    def __init__(
        self,
        client: Any,
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
        self.primary_attempts = 0

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
        user_text = "\n".join(
            str(message.get("content") or "")
            for message in message_list
            if message.get("role") == "user"
        )
        is_patch = "evidence patch 修复器" in system_text
        is_repair = "结构化输出修复器" in system_text
        if is_patch:
            kind = "patch"
        elif is_repair:
            kind = "repair"
        else:
            self.primary_attempts += 1
            kind = "primary" if self.primary_attempts == 1 else "retry"
        original_raw = None
        validation_error = None
        patch_claim_ids: list[str] = []
        if is_patch:
            try:
                patch_payload = json.loads(user_text)
                patch_claim_ids = [
                    str(item.get("claim_id"))
                    for item in patch_payload.get("quote_errors") or []
                    if isinstance(item, dict)
                ]
            except (TypeError, ValueError):
                patch_claim_ids = []
        elif is_repair:
            marker = "原始输出：\n"
            if marker in user_text:
                original_raw = user_text.split(marker, 1)[1]
                if "\n\n校验错误：" in original_raw:
                    original_raw, validation_error = original_raw.split("\n\n校验错误：", 1)
                    validation_error = validation_error.split("\n\n请返回修复后的 JSON", 1)[0]
        index = self.recorder.start_call(
            case_id=self.context["case_id"],
            run_id=self.context["run_id"],
            metric=self.metric,
            kind=kind,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_version=PROMPT_VERSION,
            prompt_sha256=self.metric_sha,
            system_prompt_sha256=sha256_text(system_text),
            system_head=system_text[:200],
            original_raw=original_raw,
            validation_error=validation_error,
            patch_claim_ids=patch_claim_ids,
        )
        try:
            response = await self.client.chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception as exc:  # noqa: BLE001
            self.recorder.finish_call(index, error=f"{type(exc).__name__}: {exc}")
            raise
        self.recorder.finish_call(
            index,
            content=response.content,
            response_model=getattr(response, "model", None),
            usage=getattr(response, "usage", None),
            latency_ms=getattr(response, "latency_ms", None),
        )
        return response


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def cost_cny(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * PRICE_INPUT + output_tokens * PRICE_OUTPUT


def in_target(value: float | None, target: Any) -> bool:
    if value is None or not isinstance(target, list) or len(target) != 2:
        return False
    return float(target[0]) <= float(value) <= float(target[1])


def normalized(text: str) -> str:
    return "".join(str(text).split())


def synthetic_trace(case: dict[str, Any]) -> RagTrace:
    case_id = case["id"]
    return RagTrace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"m1d6:v125:failure-mode:{case_id}"),
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
        "judge_config": dict(outcome.judge_config or {}),
        "details": dict(outcome.details or {}),
        "raw_output": outcome.raw_output,
    }


def by_metric(outcomes: list[Any]) -> dict[str, Any]:
    return {outcome.metric_name: outcome for outcome in outcomes}


def validate_fingerprint(outcomes: list[Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "faithfulness_strict": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
    }
    for outcome in outcomes:
        config = outcome.judge_config or {}
        if config.get("prompt_version") != PROMPT_VERSION:
            errors.append(f"{outcome.metric_name}: prompt_version")
        if config.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{outcome.metric_name}: schema_version")
        if config.get("metric_version") != METRIC_VERSION:
            errors.append(f"{outcome.metric_name}: metric_version")
        if config.get("rubric_version") != RUBRIC_VERSION:
            errors.append(f"{outcome.metric_name}: rubric_version")
        if config.get("temperature") not in (0.0, 0):
            errors.append(f"{outcome.metric_name}: temperature")
        if config.get("max_tokens") != 8192:
            errors.append(f"{outcome.metric_name}: max_tokens")
        if config.get("model") not in (None, "qwen-max"):
            errors.append(f"{outcome.metric_name}: model")
        if outcome.metric_name in {"faithfulness", "faithfulness_strict"}:
            if config.get("contract_repair_version") != PROMPT_VERSION:
                errors.append(f"{outcome.metric_name}: contract_repair_version")
            if config.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
                errors.append(f"{outcome.metric_name}: quote_validator")
        expected_sha = expected.get(outcome.metric_name)
        if expected_sha and config.get("prompt_sha256") != expected_sha:
            errors.append(f"{outcome.metric_name}: prompt_sha256")
    return errors


def validate_ledger_case(ledger: LedgerWriter, case_id: str) -> list[str]:
    expected = {
        "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
    }
    errors: list[str] = []
    for record in ledger.entries:
        if record.get("event") != "started" or record.get("case_id") != case_id:
            continue
        if record.get("kind") not in {"primary", "retry"}:
            continue
        metric = str(record.get("metric") or "")
        expected_sha = expected.get(metric)
        if expected_sha and record.get("system_prompt_sha256") != expected_sha:
            errors.append(f"{case_id}/{metric}: system_prompt_sha256")
    return sorted(set(errors))


def direct_exemption_quote(quote: str) -> bool:
    text = normalized(quote)
    if any(marker in text for marker in SPECIFIC_GOODS_MARKERS):
        return False
    return (
        "质量问题" in text
        and any(marker in text for marker in EXEMPTION_MARKERS)
        and ("7天" in text or "七天" in text or "无理由" in text)
    )


def normalize_initial_claims(initial_output: str | None) -> list[dict[str, Any]]:
    if not initial_output:
        return []
    try:
        payload = json.loads(extract_json_text(initial_output))
        claims = payload.get("claims") or []
    except (TypeError, ValueError):
        return []
    result = []
    for index, claim in enumerate(claims, 1):
        result.append(
            {
                "claim_id": str(claim.get("claim_id") or f"cl{index}"),
                "raw_claim_id": claim.get("claim_id"),
                "claim": claim.get("claim"),
                "claim_type": claim.get("claim_type"),
                "claim_subtype": claim.get("claim_subtype"),
                "support_status": claim.get("support_status"),
                "is_contradictory": claim.get("is_contradictory"),
                "contradiction_with": claim.get("contradiction_with") or [],
                "evidence_refs": claim.get("evidence_refs") or [],
            }
        )
    return result


def preview_counts(claims: list[dict[str, Any]]) -> dict[str, Any]:
    factual = [c for c in claims if c.get("claim_type") == "factual_claim"]
    supported = [c for c in factual if c.get("support_status") == "supported"]
    unsupported = [c for c in factual if c.get("support_status") == "unsupported"]
    insufficient = [
        c for c in factual if c.get("support_status") == "insufficient_evidence"
    ]
    scorable = len(factual)
    return {
        "scorable_claim_count": scorable,
        "supported_count": len(supported),
        "unsupported_count": len(unsupported),
        "insufficient_evidence_count": len(insufficient),
        "non_factual_count": len(claims) - scorable,
        "f_preview": round(len(supported) / scorable, 6) if scorable else None,
        "note": "preview ignores quote validity; not a Service F score",
    }


def classify_invalid(
    outcome: Any,
    contract: dict[str, Any] | None = None,
) -> str | None:
    if outcome is None or outcome.status not in {"invalid", "failed"}:
        return None
    contract = contract or {}
    final_errors = contract.get("final_errors") or []
    code = ""
    validation = ""
    if final_errors:
        code = str(final_errors[0].get("code") or "")
        validation = str(final_errors[0].get("validation_errors") or "").lower()
    if code == "patch_schema_invalid" and (
        "input_value=none" in validation or "evidence_refs" in validation
    ):
        return "patch_null"
    if code == "initial_schema_invalid":
        return "initial_schema_invalid"
    if code in {"patch_refused", "patch_refusal_incomplete", "patch_refusal_invalid"}:
        return "patch_refusal"
    if code in {"patch_quote_invalid", "mixed_sentence_requires_review"}:
        return "quote_continuity"
    if "quote_not_found" in validation or "quote_not_found" in str(
        outcome.details.get("errors") or ""
    ):
        return "quote_continuity"
    if final_errors:
        return "other"
    if outcome.invalid_reason == "contract_violation":
        return "other"
    return "other"


def targets_for_case(target_doc: dict[str, Any], case_id: str) -> dict[str, Any]:
    def find(obj: Any) -> Any:
        if isinstance(obj, dict):
            if obj.get("case_id") == case_id:
                return obj
            for value in obj.values():
                found = find(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = find(value)
                if found:
                    return found
        return None

    found = find(target_doc) or {}
    return dict(found.get("targets") or {})


def case_record(
    *,
    case_id: str,
    group: str,
    category: str,
    outcomes: list[Any],
    recorder: CallRecorder,
    targets: dict[str, Any],
    contexts: list[str],
) -> dict[str, Any]:
    outcomes_by_name = by_metric(outcomes)
    f = outcomes_by_name.get("faithfulness")
    c = outcomes_by_name.get("answer_correctness")
    r = outcomes_by_name.get("answer_relevancy")
    f_details = getattr(f, "details", {}) or {}
    f_contract = f_details.get("agent_contract") or {}
    c_contract = (getattr(c, "details", {}) or {}).get("agent_contract") or {}
    claims = list(f_details.get("claims") or [])
    calls = recorder.for_case(case_id)
    primary = next(
        (
            call
            for call in reversed(calls)
            if call["metric"] == "faithfulness"
            and call["kind"] in {"primary", "retry"}
            and call.get("content")
        ),
        None,
    )
    initial_output = primary.get("content") if primary else None
    initial_claims = normalize_initial_claims(initial_output)
    metrics = {
        "faithfulness": {
            "status": getattr(f, "status", None),
            "score": getattr(f, "score", None),
            "target": targets.get("F"),
            "target_hit": in_target(getattr(f, "score", None), targets.get("F")),
            "invalid_class": classify_invalid(f, f_contract),
        },
        "answer_correctness": {
            "status": getattr(c, "status", None),
            "score": getattr(c, "score", None),
            "target": targets.get("C"),
            "target_hit": in_target(getattr(c, "score", None), targets.get("C")),
            "invalid_class": classify_invalid(c),
        },
        "answer_relevancy": {
            "status": getattr(r, "status", None),
            "score": getattr(r, "score", None),
            "target": targets.get("R"),
            "target_hit": in_target(getattr(r, "score", None), targets.get("R")),
            "invalid_class": classify_invalid(r),
        },
    }
    record: dict[str, Any] = {
        "case_id": case_id,
        "group": group,
        "category": category,
        "targets": targets,
        "metrics": metrics,
        "f_counts": {
            key: f_details.get(key)
            for key in (
                "claim_count",
                "supported_count",
                "unsupported_count",
                "insufficient_evidence_count",
                "non_factual_count",
                "scorable_claim_count",
            )
        },
        "claims": claims,
        "initial_claims": initial_claims,
        "initial_preview": preview_counts(initial_claims),
        "agent_contract": f_contract,
        "c_contract": c_contract,
        "validation_errors": f_details.get("validation_errors") or [],
        "quote_precheck_errors": list(f_contract.get("quote_precheck_errors") or []),
        "mixed_sentence_warnings": list(
            f_contract.get("mixed_sentence_warnings") or []
        ),
        "patch": {
            "triggered": bool(f_contract.get("repair_triggered")),
            "applied_claims": list(f_contract.get("patch_applied_claims") or []),
            "refusal": f_contract.get("patch_refusal"),
            "missing_claims": list(f_contract.get("patch_missing_claims") or []),
            "unsupported_quote_claims": list(
                f_contract.get("patch_unsupported_quote_claims") or []
            ),
            "final_errors": list(f_contract.get("final_errors") or []),
        },
        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
        "call_summary": recorder.summary_for_case(case_id),
        "fingerprint_errors": validate_fingerprint(outcomes)
        + validate_ledger_case(recorder.ledger, case_id),
        "credential_failure": any(
            outcome.details.get("failure_kind") == "credential"
            or str(outcome.error_type or "").startswith("LLMCredential")
            for outcome in outcomes
        ),
    }
    if case_id == "Q23":
        cl1 = next(
            (claim for claim in initial_claims if claim.get("claim_id") == "cl1"),
            None,
        )
        derived = [
            claim for claim in initial_claims if claim.get("claim_subtype") == "derived"
        ]
        record["q23"] = {
            "cl1": cl1,
            "derived_claims": derived,
            "derived_count": len(derived),
            "initial_preview": preview_counts(initial_claims),
            "premise_insufficient_conclusion_supported": any(
                "第2天" in normalized(claim.get("claim") or "")
                or "第 2 天" in normalized(claim.get("claim") or "")
                for claim in initial_claims
                if claim.get("support_status") == "insufficient_evidence"
            )
            and any(
                "已超出" in normalized(claim.get("claim") or "")
                for claim in derived
                if claim.get("support_status") == "supported"
            ),
        }
    if case_id == "Q21":
        exemption_claims = []
        for claim in claims:
            text = normalized(claim.get("claim") or "")
            if "质量问题" not in text:
                continue
            if not any(marker in text for marker in ("7天", "七天", "限制")):
                continue
            quotes = [
                str(ref.get("quote") or "")
                for ref in (claim.get("evidence_refs") or [])
            ]
            exemption_claims.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "claim": claim.get("claim"),
                    "support_status": claim.get("support_status"),
                    "quotes": quotes,
                    "direct_exemption_quote": any(
                        direct_exemption_quote(quote) for quote in quotes
                    ),
                    "forbidden_quote": any(
                        ("运费" in quote or "换货" in quote)
                        and not direct_exemption_quote(quote)
                        for quote in quotes
                    ),
                }
            )
        record["q21"] = {
            "exemption_claims": exemption_claims,
            "forbidden_quote": any(
                item["forbidden_quote"] for item in exemption_claims
            ),
            "evaluable": getattr(f, "status", None) == "evaluated",
        }
    if case_id == "Q11":
        quote_checks = []
        for claim in claims:
            for ref in claim.get("evidence_refs") or []:
                quote = str(ref.get("quote") or "")
                quote_checks.append(
                    {
                        "claim_id": claim.get("claim_id"),
                        "context_id": ref.get("context_id"),
                        "quote": quote,
                        "contiguous_substring": any(
                            quote and quote in context for context in contexts
                        ),
                        "has_ellipsis": "…" in quote or "..." in quote,
                    }
                )
        record["q11"] = {
            "quote_checks": quote_checks,
            "evaluable": getattr(f, "status", None) == "evaluated",
        }
    return record


def call_matrix() -> dict[str, Any]:
    return {
        "cases": len(CASE_IDS),
        "runs_per_case": 1,
        "primary": 30,
        "patch_reserve": 10,
        "retry_reserve": 3,
        "max_judge_calls": MAX_JUDGE_CALLS,
        "ceiling_cny": CEILING_CNY,
        "hg_repeats": False,
    }


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(BASE), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def git_check() -> dict[str, Any]:
    head = run_command("rev-parse", "HEAD")
    commits = {
        "freeze": run_command("cat-file", "-e", f"{EXPECTED_FREEZE_COMMIT}^{{commit}}"),
        "agent": run_command("cat-file", "-e", f"{EXPECTED_AGENT_COMMIT}^{{commit}}"),
        "test_fix": run_command(
            "cat-file", "-e", f"{EXPECTED_TEST_FIX_COMMIT}^{{commit}}"
        ),
        "implementation_report": run_command(
            "cat-file", "-e", f"{EXPECTED_IMPLEMENTATION_REPORT_COMMIT}^{{commit}}"
        ),
        "design": run_command("cat-file", "-e", f"{EXPECTED_DESIGN_COMMIT}^{{commit}}"),
    }
    frozen_diff = run_command(
        "diff",
        "--quiet",
        EXPECTED_FREEZE_COMMIT,
        "--",
        "backend/app/prompts/rag_judge/v1.2.5",
        "backend/app/prompts/rag_judge/v1.2.4",
        "backend/app/agents/rag_judge_agent.py",
        "backend/app/services/rag_judge_service.py",
        "backend/app/schemas/agents/rag_judge.py",
        "backend/app/schemas/agents/rag_judge_patch.py",
        "backend/app/schemas/agents/rag_judge_patch_v125.py",
        "backend/app/schemas/agents/rag_judge_evidence.py",
    )
    errors: list[str] = []
    if head.returncode != 0:
        errors.append(f"git head={head.returncode}")
    if frozen_diff.returncode != 0:
        errors.append("frozen assets changed since freeze")
    for name, result in commits.items():
        if result.returncode != 0:
            errors.append(f"{name}_commit missing")
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "commits_present": {name: r.returncode == 0 for name, r in commits.items()},
        "frozen_assets_unchanged_since_freeze": frozen_diff.returncode == 0,
        "errors": errors,
    }


def application_checks(application: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    meta = application.get("meta") or {}
    run_config = application.get("run_config") or {}
    budget = application.get("budget") or {}
    cases = application.get("cases") or []
    expected_meta = {
        "status": "approved",
        "scope": "failure_mode_diagnostic",
        "case_count": 10,
        "runs_per_case": 1,
        "hg_repeats": False,
        "no_repeats": True,
        "not_approved_for_10_gate_or_40": True,
        "judge_run": False,
        "runtime_activated": False,
        "diagnostic_only": True,
        "counts_toward_10": False,
        "prompt_version": PROMPT_VERSION,
        "prompt_status": "frozen",
        "prompt_active": False,
        "freeze_commit": EXPECTED_FREEZE_COMMIT,
        "agent_commit": EXPECTED_AGENT_COMMIT,
        "test_fix_commit": EXPECTED_TEST_FIX_COMMIT,
        "implementation_report_commit": EXPECTED_IMPLEMENTATION_REPORT_COMMIT,
        "design_commit": EXPECTED_DESIGN_COMMIT,
        "manifest_sha256": EXPECTED_MANIFEST_SHA,
        "validation_sha256": EXPECTED_VALIDATION_SHA,
        "leakage_audit_sha256": EXPECTED_LEAKAGE_AUDIT_SHA,
        "patch_schema_sha256": EXPECTED_PATCH_SCHEMA_SHA,
        "patch_example_sha256": EXPECTED_PATCH_EXAMPLE_SHA,
        "quote_validator_sha256": EXPECTED_QUOTE_VALIDATOR_SHA,
        "fixture_sha256": EXPECTED_FIXTURE_SHA,
        "target_sha256": EXPECTED_TARGET_SHA,
        "labels_sha256": EXPECTED_LABELS_SHA,
        "default_prompt_version": DEFAULT_PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "metric_version": METRIC_VERSION,
        "ledger_file": "docs/repair/phase3e/m1d6-v125-failure-mode-ledger.jsonl",
        "ledger_initial_sha256": EXPECTED_LEDGER_INITIAL_SHA,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            errors.append(f"application meta.{key}={meta.get(key)!r}")
    if meta.get("prompt_sha256") != EXPECTED_PROMPT_SHA:
        errors.append("application prompt_sha256")
    if meta.get("leakage_findings") != 0:
        errors.append("application leakage_findings")
    if run_config.get("judge_prompt_version") != PROMPT_VERSION:
        errors.append("application judge_prompt_version")
    if run_config.get("default_prompt_version") != DEFAULT_PROMPT_VERSION:
        errors.append("application default_prompt_version")
    if (
        run_config.get("runs_per_case") != 1
        or run_config.get("hg_repeats") is not False
    ):
        errors.append("application runs/hg_repeats")
    if run_config.get("session") is not None:
        errors.append("application session")
    service_path = run_config.get("service_path") or {}
    if service_path.get("creates_run") is not False:
        errors.append("application creates_run")
    if service_path.get("writes_db") is not False:
        errors.append("application writes_db")
    for key in ("no_rag_call", "no_platform_run", "no_db_write", "no_weknora_call"):
        if run_config.get(key) is not True:
            errors.append(f"application {key}")
    if budget.get("primary_judge_calls") != 30:
        errors.append("application primary_judge_calls")
    if budget.get("patch_reserve") != 10:
        errors.append("application patch_reserve")
    if budget.get("retry_reserve") != 3:
        errors.append("application retry_reserve")
    if budget.get("max_judge_calls") != MAX_JUDGE_CALLS:
        errors.append("application max_judge_calls")
    if budget.get("ceiling_cny") != CEILING_CNY:
        errors.append("application ceiling_cny")
    case_ids = [case.get("case_id") for case in cases]
    if case_ids != list(CASE_IDS):
        errors.append(f"application case_ids={case_ids!r}")
    return errors


def manifest_checks(manifest: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("version") != PROMPT_VERSION:
        errors.append("manifest version")
    if manifest.get("status") != "frozen" or manifest.get("frozen") is not True:
        errors.append("manifest not frozen")
    if manifest.get("active") is not False:
        errors.append("manifest active")
    if manifest.get("runtime_active") is not False:
        errors.append("manifest runtime_active")
    if manifest.get("default_prompt_version") != DEFAULT_PROMPT_VERSION:
        errors.append("manifest default")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("manifest schema")
    if manifest.get("rubric_version") != RUBRIC_VERSION:
        errors.append("manifest rubric")
    if manifest.get("prompts") != EXPECTED_PROMPT_SHA:
        errors.append("manifest prompts")
    if manifest.get("patch_schema_sha256") != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append("manifest patch schema")
    if manifest.get("patch_example_sha256") != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append("manifest patch example")
    if manifest.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append("manifest quote validator")
    if (manifest.get("leakage_audit") or {}).get("findings") != 0:
        errors.append("manifest leakage")
    if validation.get("status") != "pass":
        errors.append("validation status")
    if validation.get("prompt_version") != PROMPT_VERSION:
        errors.append("validation prompt_version")
    if validation.get("manifest_sha256") != EXPECTED_MANIFEST_SHA:
        errors.append("validation manifest")
    if validation.get("patch_schema_sha256") != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append("validation patch schema")
    if validation.get("patch_example_sha256") != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append("validation patch example")
    if validation.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append("validation quote validator")
    failed = [c.get("check") for c in validation.get("checks") or [] if not c.get("ok")]
    if failed:
        errors.append(f"validation failed checks={failed}")
    if len(validation.get("checks") or []) != 28:
        errors.append("validation check count")
    return errors


def budget_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="m1d6-v125-fm-budget-") as tmp:
        path = Path(tmp) / "ledger.jsonl"
        path.write_bytes(b"")
        ledger = LedgerWriter(path, EXPECTED_LEDGER_INITIAL_SHA)
        for index in range(MAX_JUDGE_CALLS):
            seq = ledger.start(
                case_id="SELFTEST",
                run_id=f"R{index + 1}",
                metric="faithfulness",
                kind="primary",
                model_requested="qwen-max",
                temperature=0.0,
                max_tokens=8192,
                prompt_version=PROMPT_VERSION,
                prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_head="selftest",
            )
            ledger.finish(
                seq,
                status="ok",
                response_model="fake",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
                latency_ms=1.0,
                content="{}",
                error=None,
            )
        rejected = False
        try:
            ledger.start(
                case_id="SELFTEST",
                run_id="R44",
                metric="faithfulness",
                kind="primary",
                model_requested="qwen-max",
                temperature=0.0,
                max_tokens=8192,
                prompt_version=PROMPT_VERSION,
                prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_head="selftest",
            )
        except BudgetExceeded:
            rejected = True
        errors = []
        if ledger.attempts != MAX_JUDGE_CALLS:
            errors.append(f"attempts={ledger.attempts}")
        if ledger.uncertain_calls != 0:
            errors.append(f"uncertain={ledger.uncertain_calls}")
        if not rejected:
            errors.append("44th call not rejected")
        return {
            "ok": not errors,
            "errors": errors,
            "attempts": ledger.attempts,
            "uncertain_calls": ledger.uncertain_calls,
            "forty_fourth_rejected": rejected,
            "max_judge_calls": MAX_JUDGE_CALLS,
            "ceiling_cny": CEILING_CNY,
        }


def preflight() -> dict[str, Any]:
    application = load_json(APPLICATION_FILE)
    fixture = load_json(FIXTURE_FILE)
    target = load_json(TARGET_FILE)
    labels = load_json(LABELS_FILE)
    manifest = load_json(MANIFEST_FILE)
    validation = load_json(VALIDATION_FILE)
    leakage = load_json(LEAKAGE_AUDIT_FILE)
    application_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    target_sha = sha256_bytes(TARGET_FILE.read_bytes())
    labels_sha = sha256_bytes(LABELS_FILE.read_bytes())
    manifest_sha = sha256_bytes(MANIFEST_FILE.read_bytes())
    validation_sha = sha256_bytes(VALIDATION_FILE.read_bytes())
    leakage_sha = sha256_bytes(LEAKAGE_AUDIT_FILE.read_bytes())
    patch_schema_sha = sha256_bytes(PATCH_SCHEMA_FILE.read_bytes())
    prompt_sha = {
        name: sha256_bytes((PROMPT_DIR / name).read_bytes())
        for name in EXPECTED_PROMPT_SHA
    }
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=PROMPT_VERSION)
    patch_example_sha = sha256_text(agent._patch_example_v125() or "")
    quote_sha = quote_validator_sha256()
    if not LEDGER_FILE.exists():
        LEDGER_FILE.write_bytes(b"")
    ledger_bytes = LEDGER_FILE.read_bytes()
    ledger_sha = sha256_bytes(ledger_bytes)
    git = git_check()
    budget_test = budget_self_test()

    errors: list[str] = []
    if application_sha != EXPECTED_APPLICATION_SHA:
        errors.append(f"application_sha={application_sha}")
    if fixture_sha != EXPECTED_FIXTURE_SHA:
        errors.append("fixture_sha")
    if target_sha != EXPECTED_TARGET_SHA:
        errors.append("target_sha")
    if labels_sha != EXPECTED_LABELS_SHA:
        errors.append("labels_sha")
    if manifest_sha != EXPECTED_MANIFEST_SHA:
        errors.append("manifest_sha")
    if validation_sha != EXPECTED_VALIDATION_SHA:
        errors.append("validation_sha")
    if leakage_sha != EXPECTED_LEAKAGE_AUDIT_SHA:
        errors.append("leakage_sha")
    if patch_schema_sha != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append("patch_schema_sha")
    if patch_example_sha != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append("patch_example_sha")
    if quote_sha != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append("quote_validator_sha")
    if prompt_sha != EXPECTED_PROMPT_SHA:
        errors.append("prompt_sha")
    if ledger_sha != EXPECTED_LEDGER_INITIAL_SHA:
        errors.append("ledger_initial_sha")
    if ledger_bytes:
        errors.append("ledger not empty")
    if not budget_test["ok"]:
        errors.append(f"budget_self_test={budget_test['errors']}")
    if leakage.get("status") != "pass" or leakage.get("finding_count") != 0:
        errors.append("leakage audit")
    errors.extend(application_checks(application))
    errors.extend(manifest_checks(manifest, validation))
    errors.extend(git["errors"])
    if settings.DEFAULT_LLM_MODEL != "qwen-max":
        errors.append("model")
    if settings.DEFAULT_TEMPERATURE != 0.0:
        errors.append("temperature")
    if settings.RAG_JUDGE_MAX_TOKENS != 8192:
        errors.append("max_tokens")
    if settings.RAG_JUDGE_PROMPT_VERSION != DEFAULT_PROMPT_VERSION:
        errors.append("default prompt version")
    fixture_cases = {case["id"] for case in fixture.get("cases") or []}
    for case_id in CASE_IDS:
        if case_id not in fixture_cases:
            errors.append(f"fixture missing {case_id}")
    return {
        "application_sha256": application_sha,
        "fixture_sha256": fixture_sha,
        "target_sha256": target_sha,
        "labels_sha256": labels_sha,
        "manifest_sha256": manifest_sha,
        "validation_sha256": validation_sha,
        "leakage_audit_sha256": leakage_sha,
        "leakage_findings": leakage.get("finding_count"),
        "prompt_sha256": prompt_sha,
        "patch_schema_sha256": patch_schema_sha,
        "patch_example_sha256": patch_example_sha,
        "quote_validator_sha256": quote_sha,
        "ledger_file": str(LEDGER_FILE.relative_to(BASE)),
        "ledger_initial_sha256": ledger_sha,
        "ledger_empty": not ledger_bytes,
        "budget_self_test": budget_test,
        "git_head": git["head"],
        "freeze_commit": EXPECTED_FREEZE_COMMIT,
        "agent_commit": EXPECTED_AGENT_COMMIT,
        "test_fix_commit": EXPECTED_TEST_FIX_COMMIT,
        "implementation_report_commit": EXPECTED_IMPLEMENTATION_REPORT_COMMIT,
        "design_commit": EXPECTED_DESIGN_COMMIT,
        "frozen_assets_unchanged_since_freeze": git[
            "frozen_assets_unchanged_since_freeze"
        ],
        "call_matrix": call_matrix(),
        "errors": errors,
        "application": application,
        "fixture": fixture,
        "target": target,
        "labels": labels,
        "manifest": manifest,
        "validation": validation,
        "leakage": leakage,
    }


def dry_run_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "ok": not result["errors"],
        "errors": result["errors"],
        "application_sha256": result["application_sha256"],
        "prompt_version": PROMPT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "f_sha256": result["prompt_sha256"]["faithfulness.txt"],
        "c_sha256": result["prompt_sha256"]["answer_correctness.txt"],
        "r_sha256": result["prompt_sha256"]["answer_relevancy.txt"],
        "patch_schema_sha256": result["patch_schema_sha256"],
        "patch_example_sha256": result["patch_example_sha256"],
        "quote_validator_sha256": result["quote_validator_sha256"],
        "manifest_sha256": result["manifest_sha256"],
        "validation_sha256": result["validation_sha256"],
        "leakage_audit_sha256": result["leakage_audit_sha256"],
        "leakage_findings": result["leakage_findings"],
        "fixture_sha256": result["fixture_sha256"],
        "target_sha256": result["target_sha256"],
        "labels_sha256": result["labels_sha256"],
        "freeze_commit": result["freeze_commit"],
        "agent_commit": result["agent_commit"],
        "git_head": result["git_head"],
        "frozen_assets_unchanged_since_freeze": result[
            "frozen_assets_unchanged_since_freeze"
        ],
        "ledger_file": result["ledger_file"],
        "ledger_initial_sha256": result["ledger_initial_sha256"],
        "ledger_empty": result["ledger_empty"],
        "budget": result["call_matrix"],
        "budget_self_test": result["budget_self_test"],
        "cases": list(CASE_IDS),
        "llm_calls": 0,
        "judge_runs": 0,
    }


async def run_one(
    *,
    recorder: CallRecorder,
    real_llm: LLMClient,
    fixture_case: dict[str, Any],
    case_id: str,
    effective_prompts: list[dict[str, Any]],
) -> list[Any]:
    context = {"case_id": case_id, "run_id": case_id}

    def factory(metric: str) -> RagJudgeAgent:
        loaded = load_judge_prompt(PROMPT_VERSION, metric)
        loaded_sha = sha256_text(loaded)
        expected_sha = EXPECTED_PROMPT_SHA[f"{metric}.txt"]
        effective_prompts.append(
            {
                "case_id": case_id,
                "metric": metric,
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": loaded_sha,
                "expected_prompt_sha256": expected_sha,
            }
        )
        return RagJudgeAgent(
            metric,  # type: ignore[arg-type]
            prompt_version=PROMPT_VERSION,
            llm=InstrumentedLLM(
                real_llm,
                recorder,
                context,
                metric=metric,
                metric_sha=loaded_sha,
            ),
        )

    return await judge_trace(
        session=None,
        trace=synthetic_trace(fixture_case),
        item=SimpleNamespace(gold_answer=fixture_case["gold_answer"]),
        metrics=None,
        prompt_version=PROMPT_VERSION,
        agent_factory=factory,
    )


def dataset_case(fixture: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(case for case in fixture["cases"] if case["id"] == case_id)


def build_results(
    *,
    preflight_result: dict[str, Any],
    recorder: CallRecorder,
    ledger: LedgerWriter,
    cases: list[dict[str, Any]],
    effective_prompts: list[dict[str, Any]],
    stop_reason: str | None,
    stop_codes: list[str],
) -> dict[str, Any]:
    completed = [case["case_id"] for case in cases]
    missing = [case_id for case_id in CASE_IDS if case_id not in completed]
    invalid_classes: Counter[str] = Counter()
    invalid_cases: list[str] = []
    valid_cases: list[str] = []
    for case in cases:
        metrics = case["metrics"]
        any_invalid = False
        for metric in metrics.values():
            cls = metric.get("invalid_class")
            if cls:
                invalid_classes[cls] += 1
                any_invalid = True
        if any_invalid:
            invalid_cases.append(case["case_id"])
        else:
            valid_cases.append(case["case_id"])
    if stop_reason:
        status = "stopped"
    elif missing:
        status = "stopped"
        stop_reason = f"unprocessed cases: {missing}"
        stop_codes = ["unprocessed_case"]
    else:
        status = "collected"
    ledger_summary = ledger.summary()
    if ledger.uncertain_calls and "ledger_integrity" not in stop_codes:
        stop_codes = list(dict.fromkeys([*stop_codes, "ledger_integrity"]))
    if ledger_summary["cost_cny"] > CEILING_CNY and "budget_ceiling" not in stop_codes:
        stop_codes = list(dict.fromkeys([*stop_codes, "budget_ceiling"]))
    if ledger.attempts > MAX_JUDGE_CALLS and "budget_ceiling" not in stop_codes:
        stop_codes = list(dict.fromkeys([*stop_codes, "budget_ceiling"]))
    if stop_codes and not stop_reason:
        stop_reason = "ledger/budget issue: " + ", ".join(stop_codes)
        status = "stopped"
    cluster = (
        "concentrated_q23_q21_q11"
        if invalid_cases
        and set(invalid_cases).issubset({"Q23", "Q21", "Q11"})
        and len(valid_cases) == 7
        else "systemic"
        if len(invalid_cases) >= 5
        else "mixed"
        if invalid_cases
        else "no_invalid"
    )
    results = {
        "meta": {
            "name": "m1d6-v1.2.5-failure-mode-results",
            "status": status,
            "diagnostic_only": True,
            "counts_toward_10": False,
            "pass_written": False,
            "date": "2026-11-24",
            "application_sha256": preflight_result["application_sha256"],
            "prompt_version": PROMPT_VERSION,
            "prompt_status": "frozen",
            "prompt_active": False,
            "rubric_version": RUBRIC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "metric_version": METRIC_VERSION,
            "default_prompt_version": DEFAULT_PROMPT_VERSION,
            "manifest_sha256": preflight_result["manifest_sha256"],
            "validation_sha256": preflight_result["validation_sha256"],
            "leakage_audit_sha256": preflight_result["leakage_audit_sha256"],
            "leakage_findings": preflight_result["leakage_findings"],
            "fixture_sha256": preflight_result["fixture_sha256"],
            "target_sha256": preflight_result["target_sha256"],
            "labels_sha256": preflight_result["labels_sha256"],
            "patch_schema_sha256": preflight_result["patch_schema_sha256"],
            "patch_example_sha256": preflight_result["patch_example_sha256"],
            "quote_validator_sha256": preflight_result["quote_validator_sha256"],
            "freeze_commit": preflight_result["freeze_commit"],
            "agent_commit": preflight_result["agent_commit"],
            "test_fix_commit": preflight_result["test_fix_commit"],
            "implementation_report_commit": preflight_result[
                "implementation_report_commit"
            ],
            "design_commit": preflight_result["design_commit"],
            "git_head": preflight_result["git_head"],
            "created_run": False,
            "wrote_db": False,
            "runtime_activated": False,
            "weknora_called": False,
            "rag_adapter_called": False,
            "ran_10_gate": False,
            "ran_40": False,
            "stop_triggered": bool(stop_reason),
            "stop_reason": stop_reason,
            "stop_codes": stop_codes,
            "ledger_sha256": ledger_summary["sha256"],
            "ledger_total_attempts": ledger_summary["total_attempts"],
            "ledger_finished_calls": ledger_summary["finished_calls"],
            "ledger_uncertain_calls": ledger_summary["uncertain_calls"],
            "total_judge_calls": ledger_summary["total_attempts"],
            "cost_cny": ledger_summary["cost_cny"],
            "ceiling_cny": CEILING_CNY,
            "max_judge_calls": MAX_JUDGE_CALLS,
            "budget_error": ledger_summary["budget_error"],
            "case_count": len(cases),
            "valid_cases": valid_cases,
            "invalid_cases": invalid_cases,
            "invalid_case_count": len(invalid_cases),
            "valid_case_count": len(valid_cases),
            "invalid_by_class": dict(invalid_classes),
            "d2_cluster_signal": cluster,
            "missing_cases": missing,
        },
        "preflight": {
            key: value
            for key, value in preflight_result.items()
            if key
            not in {
                "application",
                "fixture",
                "target",
                "labels",
                "manifest",
                "validation",
                "leakage",
            }
        },
        "call_matrix": call_matrix(),
        "effective_prompts": effective_prompts,
        "cases": cases,
        "ledger": ledger_summary,
    }
    return results


def render_metric_table(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "| metric | status | score | target | target hit | invalid class |",
        "|---|---|---:|---|---|---|",
    ]
    for name, payload in metrics.items():
        lines.append(
            f"| {name} | {payload.get('status')} | {payload.get('score')} | "
            f"`{payload.get('target')}` | {payload.get('target_hit')} | "
            f"`{payload.get('invalid_class')}` |"
        )
    return lines


def write_report(results: dict[str, Any], json_sha: str) -> str:
    meta = results["meta"]
    preflight = results["preflight"]
    ledger = results["ledger"]
    lines = [
        "# M1-D-6 v1.2.5 Failure-Mode Diagnostic 结果（10 条 × 1 次）",
        "",
        f"> 状态：`{meta['status']}`；diagnostic only；无 HG repeats；不写 PASS；不计入 10 条。",
        f"> application SHA：`{meta['application_sha256']}`",
        f"> ledger SHA：`{meta['ledger_sha256']}`；"
        f"total attempts：`{meta['ledger_total_attempts']}`；"
        f"uncertain calls：`{meta['ledger_uncertain_calls']}`",
        f"> 结果 JSON SHA：`{json_sha}`",
        f"> Prompt：`{meta['prompt_version']}` / `frozen` / "
        f"rubric `{meta['rubric_version']}` / schema `{meta['schema_version']}`",
        f"> F / C / R：`{preflight['prompt_sha256']['faithfulness.txt']}` / "
        f"`{preflight['prompt_sha256']['answer_correctness.txt']}` / "
        f"`{preflight['prompt_sha256']['answer_relevancy.txt']}`",
        f"> MANIFEST / validation / leakage：`{meta['manifest_sha256']}` / "
        f"`{meta['validation_sha256']}` / `{meta['leakage_audit_sha256']}`",
        f"> patch schema / example / validator：`{meta['patch_schema_sha256']}` / "
        f"`{meta['patch_example_sha256']}` / `{meta['quote_validator_sha256']}`",
        f"> agent / freeze：`{meta['agent_commit']}` / `{meta['freeze_commit']}`",
        "",
        "## 0. 结论",
        "",
        f"- cases：`{meta['case_count']}`；valid=`{meta['valid_case_count']}`；"
        f"invalid=`{meta['invalid_case_count']}`。",
        f"- F status：`{meta.get('f_status_counts')}`；"
        f"F target hit=`{meta.get('f_target_hit_cases')}`；"
        f"F target miss=`{meta.get('f_target_miss_cases')}`",
        f"- invalid cases：`{meta['invalid_cases']}`",
        f"- valid cases：`{meta['valid_cases']}`",
        f"- invalid by class：`{meta['invalid_by_class']}`",
        f"- D2 cluster signal：`{meta['d2_cluster_signal']}`",
        f"- D2 interpretation：{meta.get('d2_interpretation', '—')}",
        f"- 停止：`{meta['stop_triggered']}`；{meta['stop_reason'] or '—'}",
        "- **diagnostic_only；未创建 Run、未写 DB、未调 WeKnora/RAG adapter；"
        "未激活 v1.2.5；未跑正式 10/40。**",
        "",
        "## 1. 调用与 Ledger",
        "",
        "| 项 | 实际 | 预算/上限 |",
        "|---|---:|---:|",
        f"| Judge calls | {meta['ledger_total_attempts']} | {MAX_JUDGE_CALLS} |",
        f"| input / output tokens | {ledger['input_tokens']} / "
        f"{ledger['output_tokens']} | — |",
        f"| cost CNY | {meta['cost_cny']:.8f} | {CEILING_CNY:.2f} |",
        f"| ledger SHA | `{meta['ledger_sha256']}` | — |",
        f"| uncertain calls | `{meta['ledger_uncertain_calls']}` | 0 |",
        "",
        "### 1.1 Ledger 明细",
        "",
        "| seq | case | kind | metric | status | input | output | cost CNY |",
        "|---:|---|---|---|---|---:|---:|---:|",
    ]
    for row in ledger["rows"]:
        lines.append(
            f"| {row['seq']} | {row['case_id']} | {row['kind']} | "
            f"{row['metric']} | {row['status']} | {row['input_tokens']} | "
            f"{row['output_tokens']} | {row['cost_cny']:.8f} |"
        )
    lines.extend(
        [
            "",
            "## 2. 逐 case 结果",
            "",
            "| case | F | C | R | F hit | invalid class | targets |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for case in results["cases"]:
        metrics = case["metrics"]
        lines.append(
            f"| {case['case_id']} | {metrics['faithfulness']['status']} "
            f"({metrics['faithfulness']['score']}) | "
            f"{metrics['answer_correctness']['status']} "
            f"({metrics['answer_correctness']['score']}) | "
            f"{metrics['answer_relevancy']['status']} "
            f"({metrics['answer_relevancy']['score']}) | "
            f"{metrics['faithfulness']['target_hit']} | "
            f"`{metrics['faithfulness']['invalid_class']}` | "
            f"`{case['targets']}` |"
        )
    lines.extend(
        [
            "",
            "## 3. Invalid 分类",
            "",
            "| class | count |",
            "|---|---:|",
        ]
    )
    for name, count in sorted(meta["invalid_by_class"].items()):
        lines.append(f"| `{name}` | {count} |")
    if not meta["invalid_by_class"]:
        lines.append("| — | 0 |")
    lines.extend(
        [
            "",
            "## 4. Q23 / Q21 / Q11 失败点",
            "",
        ]
    )
    for case_id in ("Q23", "Q21", "Q11"):
        case = next((c for c in results["cases"] if c["case_id"] == case_id), None)
        if case is None:
            lines.extend([f"### {case_id}", "", "未运行/未收集。", ""])
            continue
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"- metrics：`{json.dumps(case['metrics'], ensure_ascii=False)}`",
                f"- patch：`{json.dumps(case['patch'], ensure_ascii=False)}`",
                "- initial preview：`"
                f"{json.dumps(case.get('initial_preview'), ensure_ascii=False)}`",
            ]
        )
        if case_id == "Q23":
            lines.append(
                f"- Q23 cl1：`{json.dumps(case.get('q23', {}).get('cl1'), ensure_ascii=False)}`"
            )
            lines.append(
                f"- Q23 derived_count：`{case.get('q23', {}).get('derived_count')}`"
            )
        elif case_id == "Q21":
            lines.append(
                "- Q21 exemption：`"
                f"{json.dumps(case.get('q21', {}).get('exemption_claims'), ensure_ascii=False)}`"
            )
            lines.append(f"- Q21 evaluable：`{case.get('q21', {}).get('evaluable')}`")
            lines.append(
                "- Q21 说明：豁免 claim 正确判 insufficient_evidence；"
                "F=0.8 是 target [0.6,0.7] miss，不是 invalid。"
            )
        else:
            lines.append(
                "- Q11 quote checks：`"
                f"{json.dumps(case.get('q11', {}).get('quote_checks'), ensure_ascii=False)}`"
            )
            lines.append(f"- Q11 evaluable：`{case.get('q11', {}).get('evaluable')}`")
            lines.append("- Q11 说明：F=0.8 target hit；quote checks 全部连续。")
        lines.append("")
    lines.extend(
        [
            "## 5. 其余 7 条",
            "",
            "| case | F | C | R | F hit | invalid class |",
            "|---|---|---|---|---|---|",
        ]
    )
    for case in results["cases"]:
        if case["case_id"] in {"Q23", "Q21", "Q11"}:
            continue
        metrics = case["metrics"]
        lines.append(
            f"| {case['case_id']} | {metrics['faithfulness']['status']} "
            f"({metrics['faithfulness']['score']}) | "
            f"{metrics['answer_correctness']['status']} "
            f"({metrics['answer_correctness']['score']}) | "
            f"{metrics['answer_relevancy']['status']} "
            f"({metrics['answer_relevancy']['score']}) | "
            f"{metrics['faithfulness']['target_hit']} | "
            f"`{metrics['faithfulness']['invalid_class']}` |"
        )
    lines.extend(
        [
            "",
            "## 5.1 D2 观察",
            "",
            "- invalid 3/10：Q23/Q35/Q36；不是 Q23/Q21/Q11 集中，Q21/Q11 均 valid。",
            "- 两个失败类：`initial_schema_invalid` x2（Q23/Q35，factual+absence）、"
            "`patch_null` x1（Q36）；不是单一确定性缺陷。",
            "- C/R 全部 evaluated；F target miss：Q17=0.6、Q21=0.8；"
            "Q29 F skipped(no_scorable_claims)。",
            "- 其他观察：Q35 initial preview 0.857、Q36 initial preview 1.0，"
            "失败发生在 Schema/patch，不是分数本身。",
            "- D2：`mixed`；不出 v1.2.6；评估更强模型/确定性 contract harness"
            "（factual+absence 归一化、patch null 处理）+ Q17/Q21 target 复核；"
            "known limitation 只能记录，不能作为验收路径。",
            "",
            "## 6. 停止与边界",
            "",
            f"- stop_triggered：`{meta['stop_triggered']}`",
            f"- stop_reason：{meta['stop_reason'] or '—'}",
            f"- stop_codes：`{meta['stop_codes']}`",
            f"- missing cases：`{meta['missing_cases']}`",
            "",
            "## 7. 交付声明",
            "",
            "- diagnostic only；10 条各 1 次；无 HG repeats；不是正式 10/40。",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora/RAG adapter。",
            "- 未激活 v1.2.5；默认仍 `v1.0.0`；未跑正式 10/40；不写 PASS。",
            "- 未修改 v1.2.5 frozen 资产/target/fixture。",
            "- M1-D-6 仍 `blocked`；M1-C/M1-D 未 accepted。",
            "",
        ]
    )
    return "\n".join(lines)


async def main() -> None:
    preflight_result = preflight()
    print(
        json.dumps(dry_run_payload(preflight_result), ensure_ascii=False, indent=1),
        flush=True,
    )
    if preflight_result["errors"]:
        raise SystemExit(1)
    ledger = LedgerWriter(LEDGER_FILE, EXPECTED_LEDGER_INITIAL_SHA)
    recorder = CallRecorder(ledger=ledger)
    fixture = preflight_result["fixture"]
    target_doc = preflight_result["target"]
    cases: list[dict[str, Any]] = []
    effective_prompts: list[dict[str, Any]] = []
    stop_reason: str | None = None
    stop_codes: list[str] = []
    try:
        async with LLMClient() as real_llm:
            for case_id in CASE_IDS:
                fixture_case = dataset_case(fixture, case_id)
                outcomes = await run_one(
                    recorder=recorder,
                    real_llm=real_llm,
                    fixture_case=fixture_case,
                    case_id=case_id,
                    effective_prompts=effective_prompts,
                )
                record = case_record(
                    case_id=case_id,
                    group="human_gold"
                    if case_id in {"Q01", "Q17", "Q23"}
                    else "provisional",
                    category=fixture_case.get("category") or "",
                    outcomes=outcomes,
                    recorder=recorder,
                    targets=targets_for_case(target_doc, case_id),
                    contexts=[ctx["content"] for ctx in fixture_case["contexts"]],
                )
                cases.append(record)
                print(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "metrics": {
                                k: (v.get("status"), v.get("score"))
                                for k, v in record["metrics"].items()
                            },
                            "calls": recorder.judge_calls,
                            "cost_cny": round(recorder.cost, 8),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if recorder.budget_exceeded or ledger.budget_error:
                    stop_reason = "budget_ceiling"
                    stop_codes = ["budget_ceiling"]
                    break
                if record["credential_failure"]:
                    stop_reason = "credential_failure"
                    stop_codes = ["credential_failure"]
                    break
                if record["fingerprint_errors"]:
                    stop_reason = "fingerprint_mismatch"
                    stop_codes = ["fingerprint_mismatch"]
                    break
                if ledger.uncertain_calls:
                    stop_reason = "ledger_integrity"
                    stop_codes = ["ledger_integrity"]
                    break
    except Exception as exc:  # noqa: BLE001
        stop_reason = f"runner_exception: {type(exc).__name__}: {exc}"
        stop_codes = ["runner_exception"]
    results = build_results(
        preflight_result=preflight_result,
        recorder=recorder,
        ledger=ledger,
        cases=cases,
        effective_prompts=effective_prompts,
        stop_reason=stop_reason,
        stop_codes=stop_codes,
    )
    OUT_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    json_sha = sha256_bytes(OUT_JSON.read_bytes())
    OUT_SHA.write_text(f"{json_sha}  {OUT_JSON.name}\n", encoding="utf-8", newline="\n")
    report = write_report(results, json_sha)
    OUT_MD.write_text(report, encoding="utf-8", newline="\n")
    md_sha = sha256_bytes(OUT_MD.read_bytes())
    OUT_REPORT_SHA.write_text(
        f"{md_sha}  {OUT_MD.name}\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": results["meta"]["status"],
                "valid_cases": results["meta"]["valid_cases"],
                "invalid_cases": results["meta"]["invalid_cases"],
                "invalid_by_class": results["meta"]["invalid_by_class"],
                "d2_cluster_signal": results["meta"]["d2_cluster_signal"],
                "ledger_sha256": results["meta"]["ledger_sha256"],
                "calls": results["meta"]["ledger_total_attempts"],
                "cost_cny": results["meta"]["cost_cny"],
                "json_sha256": json_sha,
                "md_sha256": md_sha,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        result = preflight()
        print(json.dumps(dry_run_payload(result), ensure_ascii=False, indent=1))
        raise SystemExit(1 if result["errors"] else 0)
    if "--report-only" in sys.argv:
        results = load_json(OUT_JSON)
        json_sha = sha256_bytes(OUT_JSON.read_bytes())
        report = write_report(results, json_sha)
        OUT_MD.write_text(report, encoding="utf-8", newline="\n")
        md_sha = sha256_bytes(OUT_MD.read_bytes())
        OUT_REPORT_SHA.write_text(
            f"{md_sha}  {OUT_MD.name}\n", encoding="utf-8", newline="\n"
        )
        print(json.dumps({"json_sha256": json_sha, "md_sha256": md_sha}, indent=1))
        raise SystemExit(0)
    asyncio.run(main())
