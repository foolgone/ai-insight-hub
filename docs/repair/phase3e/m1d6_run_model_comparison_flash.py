"""M1-D-6 v1.2.5 model comparison runner (DashScope / qwen3.8-flash, no thinking).

- 5 cases (Q23/Q35/Q36/Q17/Q21) x 1 arm x F only x 1 run.
- 5 primary + 5 patch reserve + 3 retry reserve = max 13 calls / CNY 0.60.
- judge_trace(session=None); no Run/DB/WeKnora/RAG adapter.
- diagnostic_only: invalid continues; no HG repeats; no PASS; no target change.
- append-only ledger at the LLM boundary; token-based CNY upper bound.

Dry-run (no LLM):
    python docs/repair/phase3e/m1d6_run_model_comparison_flash.py --dry-run
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

API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not API_KEY:
    raise SystemExit("DASHSCOPE_API_KEY is required for the approved DashScope run")

MODEL = "qwen3.8-flash"
PROVIDER = "dashscope"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
USER_AGENT = "ai-insight-hub-rag-judge/1.0"
ENABLE_THINKING = False

os.environ["DEEPSEEK_BASE_URL"] = BASE_URL
os.environ["DEEPSEEK_API_KEY"] = API_KEY
os.environ["DEFAULT_LLM_MODEL"] = MODEL
os.environ["DEFAULT_TEMPERATURE"] = "0.0"
os.environ["RAG_JUDGE_MAX_TOKENS"] = "8192"
os.environ["RAG_JUDGE_PROMPT_VERSION"] = "v1.0.0"

from app.agents.base import AgentConfig  # noqa: E402
from app.agents.rag_judge_agent import RagJudgeAgent, load_judge_prompt  # noqa: E402
from app.agents.structured_output import extract_json_text  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.llm import LLMClient  # noqa: E402
from app.models.rag import RagTrace  # noqa: E402
from app.schemas.agents.rag_judge_evidence import quote_validator_sha256  # noqa: E402
from app.services.rag_judge_service import judge_trace  # noqa: E402

APPLICATION_FILE = (
    BASE / "docs/repair/phase3e/m1d6-v125-model-comparison-flash-application.json"
)
PREFLIGHT_FILE = (
    BASE / "docs/repair/phase3e/m1d6-v125-model-comparison-flash-preflight.json"
)
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
BASELINE_FILE = BASE / "docs/repair/phase3e/m1d6-v125-failure-mode-results.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.5/MANIFEST.json"
VALIDATION_FILE = BASE / "docs/repair/phase3e/m1d7-prompt-v1.2.5-validation.json"
LEAKAGE_AUDIT_FILE = BASE / "docs/repair/phase3e/m1d7-prompt-leakage-audit.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.5"
PATCH_SCHEMA_FILE = BASE / "backend/app/schemas/agents/rag_judge_patch_v125.py"
LEDGER_FILE = BASE / "docs/repair/phase3e/m1d6-v125-model-comparison-flash-ledger.jsonl"
OUT_JSON = BASE / "docs/repair/phase3e/m1d6-v125-model-comparison-flash-results.json"
OUT_MD = BASE / "docs/repair/60-m1d6-v1.2.5-model-comparison-flash-results.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d6-v125-model-comparison-flash-results.sha256"
OUT_REPORT_SHA = (
    BASE / "docs/repair/phase3e/m1d6-v125-model-comparison-flash-report.sha256"
)

EXPECTED_APPLICATION_SHA = (
    "6f69e8f4f567b45e4f2cda4f75a668cd48da6225d8d5c9220828d2442fee30b5"
)
EXPECTED_PREFLIGHT_SHA = (
    "0e5925e8bb9a9c197b862a49de8da953fecf81f9455dad58ade72151d4c4f327"
)
EXPECTED_FIXTURE_SHA = (
    "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"
)
EXPECTED_TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
EXPECTED_LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
EXPECTED_BASELINE_SHA = (
    "309fa9b8306174f9f74fe7968a9aa1bc70109af140c7a465a6a52f5dc3294b50"
)
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
MAX_TEMPERATURE = 0.0
MAX_TOKENS = 8192
AGENT_TIMEOUT_SECONDS = 300.0
MAX_JUDGE_CALLS = 13
CEILING_CNY = 0.60
PRICE_INPUT_CNY_PER_MTOK = 2.4
PRICE_OUTPUT_CNY_PER_MTOK = 9.6
CASE_IDS = ("Q23", "Q35", "Q36", "Q17", "Q21")
CASE_GROUP = {"Q23": "human_gold", "Q17": "human_gold"}
FIXED_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "m1d6:flash:user")


class LedgerError(RuntimeError):
    """Ledger integrity failure."""


class BudgetExceeded(RuntimeError):
    """Raised before a call that would exceed the approved budget."""


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
    return (
        input_tokens * PRICE_INPUT_CNY_PER_MTOK / 1_000_000
        + output_tokens * PRICE_OUTPUT_CNY_PER_MTOK / 1_000_000
    )


def in_target(value: float | None, target: Any) -> bool:
    if value is None or not isinstance(target, list) or len(target) != 2:
        return False
    return float(target[0]) <= float(value) <= float(target[1])


def normalized(text: str) -> str:
    return "".join(str(text).split())


@dataclass
class LedgerWriter:
    path: Path
    expected_initial_sha256: str
    require_empty: bool = True
    _seq: int = 0
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
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
        if cost_cny(self.input_tokens, self.output_tokens) > CEILING_CNY:
            self.budget_error = (
                f"cost {cost_cny(self.input_tokens, self.output_tokens):.6f} "
                f"> {CEILING_CNY:.2f}"
            )
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
        raw_usage: dict[str, Any] | None,
        latency_ms: float | None,
        content: str | None,
        error: str | None,
        finish_reason: str | None = None,
    ) -> None:
        started = self._open.pop(seq, None)
        if started is None:
            raise LedgerError(f"finished without started seq={seq}")
        raw_usage = raw_usage or {}
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        reasoning = int(
            (raw_usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            or 0
        )
        cached = int(
            (raw_usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        )
        call_cost = cost_cny(input_tokens, output_tokens)
        record = {
            "event": "finished",
            "seq": seq,
            "call_id": started.get("call_id"),
            "timestamp": utc_now(),
            "status": status,
            "response_model": response_model,
            "usage": {
                "input": input_tokens,
                "output": output_tokens,
                "reasoning": reasoning,
                "cached": cached,
            },
            "cost_cny_upper_bound": round(call_cost, 8),
            "finish_reason": finish_reason,
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
        self.reasoning_tokens += reasoning
        self.cached_tokens += cached
        if cost_cny(self.input_tokens, self.output_tokens) > CEILING_CNY:
            self.budget_error = (
                f"cost {cost_cny(self.input_tokens, self.output_tokens):.6f} "
                f"> {CEILING_CNY:.2f}"
            )

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
                    "metric": record.get("metric"),
                    "kind": record.get("kind"),
                    "status": fin.get("status"),
                    "input_tokens": int(usage.get("input") or 0),
                    "output_tokens": int(usage.get("output") or 0),
                    "reasoning_tokens": int(usage.get("reasoning") or 0),
                    "cached_tokens": int(usage.get("cached") or 0),
                    "cost_cny_upper_bound": float(
                        fin.get("cost_cny_upper_bound") or 0.0
                    ),
                    "finish_reason": fin.get("finish_reason"),
                    "latency_ms": fin.get("latency_ms"),
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
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "cost_cny_upper_bound": round(self.cost, 8),
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
                arm="A1",
                model_requested=model,
                metric=metric,
                kind=kind,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_thinking=ENABLE_THINKING,
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
                "finish_reason": None,
                "reasoning_tokens": 0,
                "cached_tokens": 0,
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
        raw: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        record = self.calls[index]
        status = "error" if error else "ok"
        raw = raw or {}
        raw_usage = raw.get("usage") or {}
        choice = (raw.get("choices") or [{}])[0] or {}
        finish_reason = choice.get("finish_reason")
        self.ledger.finish(
            int(record["ledger_seq"]),
            status=status,
            response_model=response_model,
            usage=usage,
            raw_usage=raw_usage,
            latency_ms=latency_ms,
            content=content,
            error=error,
            finish_reason=finish_reason,
        )
        record["content"] = content
        record["response_model"] = response_model
        record["latency_ms"] = latency_ms
        record["error"] = error
        record["finish_reason"] = finish_reason
        record["reasoning_tokens"] = int(
            (raw_usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            or 0
        )
        record["cached_tokens"] = int(
            (raw_usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        )
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
            "reasoning_tokens": sum(
                int(call.get("reasoning_tokens") or 0) for call in calls
            ),
            "cached_tokens": sum(int(call.get("cached_tokens") or 0) for call in calls),
            "cost_cny_upper_bound": round(cost_cny(input_tokens, output_tokens), 8),
        }


class DashScopeFlashClient(LLMClient):
    """LLMClient that disables Qwen thinking so output fits max_tokens=8192."""

    def _build_payload(
        self,
        messages: Any,
        *,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        response_format: Any,
        stream: bool,
    ) -> dict[str, Any]:
        payload = super()._build_payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=stream,
        )
        payload["enable_thinking"] = ENABLE_THINKING
        return payload

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        headers["User-Agent"] = USER_AGENT
        return headers


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
        **kwargs: Any,
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
        except BaseException as exc:  # noqa: BLE001 - record timeout/cancel
            self.recorder.finish_call(index, error=f"{type(exc).__name__}: {exc}")
            raise
        self.recorder.finish_call(
            index,
            content=response.content,
            response_model=getattr(response, "model", None),
            usage=getattr(response, "usage", None),
            raw=getattr(response, "raw", None) or {},
            latency_ms=getattr(response, "latency_ms", None),
        )
        return response


def synthetic_trace(case: dict[str, Any]) -> RagTrace:
    case_id = case["id"]
    return RagTrace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"m1d6:flash:{case_id}"),
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
        if config.get("max_tokens") != MAX_TOKENS:
            errors.append(f"{outcome.metric_name}: max_tokens")
        if config.get("model") not in (None, MODEL):
            errors.append(f"{outcome.metric_name}: model")
        if outcome.metric_name in {"faithfulness", "faithfulness_strict"}:
            if config.get("contract_repair_version") != PROMPT_VERSION:
                errors.append(f"{outcome.metric_name}: contract_repair_version")
            if config.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
                errors.append(f"{outcome.metric_name}: quote_validator")
        expected_sha = expected.get(outcome.metric_name)
        if expected_sha and config.get("prompt_sha256") != expected_sha:
            errors.append(f"{outcome.metric_name}: prompt_sha256")
    return sorted(set(errors))


def validate_ledger_case(ledger: LedgerWriter, case_id: str) -> list[str]:
    expected_sha = EXPECTED_PROMPT_SHA["faithfulness.txt"]
    errors: list[str] = []
    for record in ledger.entries:
        if record.get("event") != "started" or record.get("case_id") != case_id:
            continue
        if record.get("kind") not in {"primary", "retry"}:
            continue
        if record.get("metric") != "faithfulness":
            continue
        if record.get("system_prompt_sha256") != expected_sha:
            errors.append(f"{case_id}/faithfulness: system_prompt_sha256")
        if record.get("model_requested") not in (None, MODEL):
            errors.append(f"{case_id}/faithfulness: model_requested")
        if record.get("enable_thinking") is not ENABLE_THINKING:
            errors.append(f"{case_id}/faithfulness: enable_thinking")
    return sorted(set(errors))


def classify_invalid(
    outcome: Any,
    contract: dict[str, Any] | None = None,
    finish_reason: str | None = None,
) -> str | None:
    if outcome is None or outcome.status not in {"invalid", "failed"}:
        return None
    if finish_reason == "length":
        return "output_truncated"
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


def primary_f_call(recorder: CallRecorder, case_id: str) -> dict[str, Any] | None:
    calls = recorder.for_case(case_id)
    return next(
        (
            call
            for call in calls
            if call["metric"] == "faithfulness"
            and call["kind"] in {"primary", "retry"}
            and call.get("content")
        ),
        None,
    )


def case_record(
    *,
    case_id: str,
    category: str,
    outcomes: list[Any],
    recorder: CallRecorder,
    targets: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    outcomes_by_name = by_metric(outcomes)
    f = outcomes_by_name.get("faithfulness")
    strict = outcomes_by_name.get("faithfulness_strict")
    f_details = getattr(f, "details", {}) or {}
    f_contract = f_details.get("agent_contract") or {}
    claims = list(f_details.get("claims") or [])
    initial = primary_f_call(recorder, case_id)
    initial_finish_reason = (initial or {}).get("finish_reason")
    initial_claims = normalize_initial_claims(
        initial.get("content") if initial else None
    )
    metrics = {
        "faithfulness": {
            "status": getattr(f, "status", None),
            "score": getattr(f, "score", None),
            "target": targets.get("F"),
            "target_hit": in_target(getattr(f, "score", None), targets.get("F")),
            "invalid_class": classify_invalid(f, f_contract, initial_finish_reason),
            "finish_reason": initial_finish_reason,
        },
        "faithfulness_strict": {
            "status": getattr(strict, "status", None),
            "score": getattr(strict, "score", None),
            "invalid_class": classify_invalid(strict),
        },
    }
    baseline_score = baseline.get("score")
    delta = None
    if isinstance(baseline_score, (int, float)) and isinstance(
        getattr(f, "score", None), (int, float)
    ):
        delta = round(float(getattr(f, "score")) - float(baseline_score), 6)
    record: dict[str, Any] = {
        "case_id": case_id,
        "group": CASE_GROUP.get(case_id, "provisional"),
        "category": category,
        "targets": targets,
        "metrics": metrics,
        "baseline": {
            "model": "qwen-max",
            "status": baseline.get("status"),
            "score": baseline_score,
            "invalid_class": baseline.get("invalid_class"),
            "score_delta": delta,
            "status_changed": baseline.get("status")
            != metrics["faithfulness"]["status"],
        },
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
        "patch": {
            "triggered": bool(f_contract.get("repair_triggered")),
            "applied_claims": list(f_contract.get("patch_applied_claims") or []),
            "refusal": f_contract.get("patch_refusal"),
            "missing_claims": list(f_contract.get("patch_missing_claims") or []),
            "unsupported_quote_claims": list(
                f_contract.get("patch_unsupported_quote_claims") or []
            ),
            "final_patch_errors": list(f_contract.get("final_errors") or []),
        },
        "calls": [
            {
                "seq": call["call_index"],
                "metric": call["metric"],
                "kind": call["kind"],
                "finish_reason": call.get("finish_reason"),
                "reasoning_tokens": call.get("reasoning_tokens"),
                "cached_tokens": call.get("cached_tokens"),
                "latency_ms": call.get("latency_ms"),
                "error": call.get("error"),
            }
            for call in recorder.for_case(case_id)
        ],
        "call_summary": recorder.summary_for_case(case_id),
        "fingerprint_errors": validate_fingerprint(outcomes)
        + validate_ledger_case(recorder.ledger, case_id),
        "credential_failure": any(
            outcome.details.get("failure_kind") == "credential"
            or str(outcome.error_type or "").startswith("LLMCredential")
            for outcome in outcomes
        ),
        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
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
            "cl1_unsupported_contradictory": bool(
                cl1
                and cl1.get("support_status") == "unsupported"
                and cl1.get("is_contradictory") is True
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
            exemption_claims.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "claim": claim.get("claim"),
                    "support_status": claim.get("support_status"),
                    "quotes": [
                        str(ref.get("quote") or "")
                        for ref in (claim.get("evidence_refs") or [])
                    ],
                }
            )
        record["q21"] = {
            "exemption_claims": exemption_claims,
            "exemption_insufficient": all(
                item["support_status"] == "insufficient_evidence"
                for item in exemption_claims
            )
            if exemption_claims
            else None,
            "evaluable": getattr(f, "status", None) == "evaluated",
        }
    return record


def call_matrix() -> dict[str, Any]:
    return {
        "cases": len(CASE_IDS),
        "arms": 1,
        "model": MODEL,
        "enable_thinking": ENABLE_THINKING,
        "runs_per_case": 1,
        "primary": 5,
        "patch_reserve": 5,
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
    arm = application.get("arm") or {}
    cases = application.get("cases") or []
    expected_meta = {
        "status": "approved",
        "scope": "model_comparison_diagnostic",
        "case_count": 5,
        "arms": 1,
        "runs_per_case_per_arm": 1,
        "hg_repeats": False,
        "no_repeats": True,
        "diagnostic_only": True,
        "counts_toward_10": False,
        "judge_run": False,
        "runtime_activated": False,
        "prompt_version": PROMPT_VERSION,
        "prompt_status": "frozen",
        "prompt_active": False,
        "default_prompt_version": DEFAULT_PROMPT_VERSION,
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
        "baseline_sha256": EXPECTED_BASELINE_SHA,
        "schema_version": SCHEMA_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "metric_version": METRIC_VERSION,
        "ledger_initial_sha256": EXPECTED_LEDGER_INITIAL_SHA,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            errors.append(f"application meta.{key}={meta.get(key)!r}")
    if meta.get("prompt_sha256") != EXPECTED_PROMPT_SHA:
        errors.append("application prompt_sha256")
    if meta.get("leakage_findings") != 0:
        errors.append("application leakage_findings")
    if arm.get("model") != MODEL:
        errors.append(f"application arm.model={arm.get('model')!r}")
    if arm.get("enable_thinking") is not ENABLE_THINKING:
        errors.append("application arm.enable_thinking")
    if arm.get("max_tokens") != MAX_TOKENS:
        errors.append("application arm.max_tokens")
    if run_config.get("no_rag_call") is not True:
        errors.append("application no_rag_call")
    if (run_config.get("service_path") or {}).get("creates_run") is not False:
        errors.append("application creates_run")
    if (run_config.get("service_path") or {}).get("writes_db") is not False:
        errors.append("application writes_db")
    if budget.get("primary_judge_calls") != 5:
        errors.append("application primary_judge_calls")
    if budget.get("patch_reserve") != 5:
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
    failed = [c.get("check") for c in validation.get("checks") or [] if not c.get("ok")]
    if failed:
        errors.append(f"validation failed checks={failed}")
    if len(validation.get("checks") or []) != 28:
        errors.append("validation check count")
    return errors


def budget_self_test() -> dict[str, Any]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="m1d6-flash-budget-") as tmp:
        path = Path(tmp) / "ledger.jsonl"
        path.write_bytes(b"")
        ledger = LedgerWriter(path, EXPECTED_LEDGER_INITIAL_SHA)
        for index in range(MAX_JUDGE_CALLS):
            seq = ledger.start(
                case_id="SELFTEST",
                run_id=f"R{index + 1}",
                arm="A1",
                model_requested=MODEL,
                metric="faithfulness",
                kind="primary",
                enable_thinking=ENABLE_THINKING,
                prompt_version=PROMPT_VERSION,
                prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_head="selftest",
            )
            ledger.finish(
                seq,
                status="ok",
                response_model=MODEL,
                usage=SimpleNamespace(input_tokens=10, output_tokens=10),
                raw_usage={"completion_tokens_details": {"reasoning_tokens": 0}},
                latency_ms=1.0,
                content="{}",
                error=None,
                finish_reason="stop",
            )
        rejected = False
        try:
            ledger.start(
                case_id="SELFTEST",
                run_id="R14",
                arm="A1",
                model_requested=MODEL,
                metric="faithfulness",
                kind="primary",
                enable_thinking=ENABLE_THINKING,
                prompt_version=PROMPT_VERSION,
                prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                system_head="selftest",
            )
        except BudgetExceeded:
            rejected = True
        if ledger.attempts != MAX_JUDGE_CALLS:
            errors.append(f"attempts={ledger.attempts}")
        if ledger.uncertain_calls != 0:
            errors.append(f"uncertain={ledger.uncertain_calls}")
        if not rejected:
            errors.append("14th call not rejected")

    with tempfile.TemporaryDirectory(prefix="m1d6-flash-ceiling-") as tmp:
        path = Path(tmp) / "ledger.jsonl"
        path.write_bytes(b"")
        ledger = LedgerWriter(path, EXPECTED_LEDGER_INITIAL_SHA)
        ceiling_rejected = False
        for index in range(MAX_JUDGE_CALLS):
            try:
                seq = ledger.start(
                    case_id="SELFTEST",
                    run_id=f"C{index + 1}",
                    arm="A1",
                    model_requested=MODEL,
                    metric="faithfulness",
                    kind="primary",
                    enable_thinking=ENABLE_THINKING,
                    prompt_version=PROMPT_VERSION,
                    prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                    system_prompt_sha256=EXPECTED_PROMPT_SHA["faithfulness.txt"],
                    system_head="selftest",
                )
            except BudgetExceeded:
                ceiling_rejected = True
                break
            ledger.finish(
                seq,
                status="ok",
                response_model=MODEL,
                usage=SimpleNamespace(input_tokens=100_000, output_tokens=100_000),
                raw_usage={"completion_tokens_details": {"reasoning_tokens": 0}},
                latency_ms=1.0,
                content="{}",
                error=None,
                finish_reason="stop",
            )
        if not ceiling_rejected:
            errors.append("ceiling stop not triggered")
        if ledger.budget_error is None:
            errors.append("ceiling budget_error missing")

    return {
        "ok": not errors,
        "errors": errors,
        "max_judge_calls": MAX_JUDGE_CALLS,
        "ceiling_cny": CEILING_CNY,
        "call_cap_rejected_14th": rejected,
        "ceiling_stop_triggered": ceiling_rejected,
    }


def transport_check() -> dict[str, Any]:
    import httpx

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    with httpx.Client(base_url=BASE_URL) as client:
        request = client.build_request(
            "POST",
            "/chat/completions",
            json={"model": MODEL, "messages": []},
            headers=headers,
        )
        return {
            "url": str(request.url),
            "user_agent": request.headers.get("user-agent"),
            "model": MODEL,
        }


def preflight() -> dict[str, Any]:
    application = load_json(APPLICATION_FILE)
    preflight_doc = load_json(PREFLIGHT_FILE)
    fixture = load_json(FIXTURE_FILE)
    target = load_json(TARGET_FILE)
    labels = load_json(LABELS_FILE)
    baseline = load_json(BASELINE_FILE)
    manifest = load_json(MANIFEST_FILE)
    validation = load_json(VALIDATION_FILE)
    leakage = load_json(LEAKAGE_AUDIT_FILE)
    application_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    preflight_sha = sha256_bytes(PREFLIGHT_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    target_sha = sha256_bytes(TARGET_FILE.read_bytes())
    labels_sha = sha256_bytes(LABELS_FILE.read_bytes())
    baseline_sha = sha256_bytes(BASELINE_FILE.read_bytes())
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
    transport = transport_check()

    errors: list[str] = []
    if application_sha != EXPECTED_APPLICATION_SHA:
        errors.append(f"application_sha={application_sha}")
    if preflight_sha != EXPECTED_PREFLIGHT_SHA:
        errors.append(f"preflight_sha={preflight_sha}")
    if fixture_sha != EXPECTED_FIXTURE_SHA:
        errors.append("fixture_sha")
    if target_sha != EXPECTED_TARGET_SHA:
        errors.append("target_sha")
    if labels_sha != EXPECTED_LABELS_SHA:
        errors.append("labels_sha")
    if baseline_sha != EXPECTED_BASELINE_SHA:
        errors.append("baseline_sha")
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
    if transport["url"] != f"{BASE_URL}/chat/completions":
        errors.append(f"transport url={transport['url']}")
    errors.extend(application_checks(application))
    errors.extend(manifest_checks(manifest, validation))
    errors.extend(git["errors"])
    if settings.DEFAULT_LLM_MODEL != MODEL:
        errors.append(f"model={settings.DEFAULT_LLM_MODEL}")
    if settings.DEFAULT_TEMPERATURE != MAX_TEMPERATURE:
        errors.append("temperature")
    if settings.RAG_JUDGE_MAX_TOKENS != MAX_TOKENS:
        errors.append("max_tokens")
    if settings.RAG_JUDGE_PROMPT_VERSION != DEFAULT_PROMPT_VERSION:
        errors.append("default prompt version")
    if preflight_doc.get("meta", {}).get("status") != "preflight_passed":
        errors.append("preflight doc status")
    fixture_cases = {case["id"] for case in fixture.get("cases") or []}
    for case_id in CASE_IDS:
        if case_id not in fixture_cases:
            errors.append(f"fixture missing {case_id}")
    baseline_cases = {case["case_id"] for case in baseline.get("cases") or []}
    for case_id in CASE_IDS:
        if case_id not in baseline_cases:
            errors.append(f"baseline missing {case_id}")
    return {
        "application_sha256": application_sha,
        "preflight_sha256": preflight_sha,
        "fixture_sha256": fixture_sha,
        "target_sha256": target_sha,
        "labels_sha256": labels_sha,
        "baseline_sha256": baseline_sha,
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
        "transport": transport,
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
        "baseline": baseline,
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
        "preflight_sha256": result["preflight_sha256"],
        "model": MODEL,
        "provider": PROVIDER,
        "base_url": BASE_URL,
        "enable_thinking": ENABLE_THINKING,
        "case_ids": list(CASE_IDS),
        "prompt_version": PROMPT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "f_sha256": result["prompt_sha256"]["faithfulness.txt"],
        "manifest_sha256": result["manifest_sha256"],
        "validation_sha256": result["validation_sha256"],
        "leakage_audit_sha256": result["leakage_audit_sha256"],
        "leakage_findings": result["leakage_findings"],
        "patch_schema_sha256": result["patch_schema_sha256"],
        "patch_example_sha256": result["patch_example_sha256"],
        "quote_validator_sha256": result["quote_validator_sha256"],
        "fixture_sha256": result["fixture_sha256"],
        "target_sha256": result["target_sha256"],
        "labels_sha256": result["labels_sha256"],
        "baseline_sha256": result["baseline_sha256"],
        "freeze_commit": result["freeze_commit"],
        "agent_commit": result["agent_commit"],
        "git_head": result["git_head"],
        "frozen_assets_unchanged_since_freeze": result[
            "frozen_assets_unchanged_since_freeze"
        ],
        "ledger_file": result["ledger_file"],
        "ledger_initial_sha256": result["ledger_initial_sha256"],
        "ledger_empty": result["ledger_empty"],
        "transport": result["transport"],
        "budget": result["call_matrix"],
        "budget_self_test": result["budget_self_test"],
        "pricing_basis": "qwen-max CNY table as flash upper bound",
        "llm_calls": 0,
        "judge_runs": 0,
    }


async def run_one(
    *,
    recorder: CallRecorder,
    llm: DashScopeFlashClient,
    fixture_case: dict[str, Any],
    case_id: str,
    effective_prompts: list[dict[str, Any]],
) -> list[Any]:
    context = {"case_id": case_id, "run_id": f"A1:{case_id}"}

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
        config = AgentConfig(
            name=f"rag_judge_{metric}",
            version=PROMPT_VERSION,
            model=MODEL,
            temperature=MAX_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            timeout=AGENT_TIMEOUT_SECONDS,
            max_retries=0,
        )
        return RagJudgeAgent(
            metric,  # type: ignore[arg-type]
            config=config,
            prompt_version=PROMPT_VERSION,
            llm=InstrumentedLLM(
                llm,
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
        metrics=["faithfulness"],
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
    f_status: Counter[str] = Counter()
    f_target_hit: list[str] = []
    f_target_miss: list[str] = []
    status_changed: list[str] = []
    truncated_cases: list[str] = []
    for case in cases:
        metrics = case["metrics"]
        f_status[str(metrics["faithfulness"]["status"])] += 1
        if metrics["faithfulness"].get("finish_reason") == "length":
            truncated_cases.append(case["case_id"])
        cls = metrics["faithfulness"].get("invalid_class")
        if cls:
            invalid_classes[cls] += 1
            invalid_cases.append(case["case_id"])
        else:
            valid_cases.append(case["case_id"])
        if metrics["faithfulness"]["status"] == "evaluated" and isinstance(
            metrics["faithfulness"].get("target"), list
        ):
            if metrics["faithfulness"]["target_hit"]:
                f_target_hit.append(case["case_id"])
            else:
                f_target_miss.append(case["case_id"])
        if case["baseline"]["status_changed"]:
            status_changed.append(case["case_id"])
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
    if ledger_summary["cost_cny_upper_bound"] > CEILING_CNY and (
        "budget_ceiling" not in stop_codes
    ):
        stop_codes = list(dict.fromkeys([*stop_codes, "budget_ceiling"]))
    if ledger.attempts > MAX_JUDGE_CALLS and "budget_ceiling" not in stop_codes:
        stop_codes = list(dict.fromkeys([*stop_codes, "budget_ceiling"]))
    if stop_codes and not stop_reason:
        stop_reason = "ledger/budget issue: " + ", ".join(stop_codes)
        status = "stopped"
    results = {
        "meta": {
            "name": "m1d6-v1.2.5-model-comparison-flash-results",
            "status": status,
            "diagnostic_only": True,
            "counts_toward_10": False,
            "pass_written": False,
            "date": "2026-11-24",
            "model": MODEL,
            "provider": PROVIDER,
            "base_url": BASE_URL,
            "enable_thinking": ENABLE_THINKING,
            "application_sha256": preflight_result["application_sha256"],
            "preflight_sha256": preflight_result["preflight_sha256"],
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
            "baseline_sha256": preflight_result["baseline_sha256"],
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
            "cost_cny_upper_bound": ledger_summary["cost_cny_upper_bound"],
            "ceiling_cny": CEILING_CNY,
            "max_judge_calls": MAX_JUDGE_CALLS,
            "budget_error": ledger_summary["budget_error"],
            "case_count": len(cases),
            "valid_cases": valid_cases,
            "invalid_cases": invalid_cases,
            "invalid_case_count": len(invalid_cases),
            "valid_case_count": len(valid_cases),
            "invalid_by_class": dict(invalid_classes),
            "f_status_counts": dict(f_status),
            "f_evaluated_count": f_status.get("evaluated", 0),
            "f_invalid_count": f_status.get("invalid", 0) + f_status.get("failed", 0),
            "f_skipped_count": f_status.get("skipped", 0),
            "f_target_hit_cases": f_target_hit,
            "f_target_miss_cases": f_target_miss,
            "baseline_status_changed_cases": status_changed,
            "truncated_cases": truncated_cases,
            "truncated_count": len(truncated_cases),
            "max_tokens": MAX_TOKENS,
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
                "baseline",
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


def write_report(results: dict[str, Any], json_sha: str) -> str:
    meta = results["meta"]
    preflight = results["preflight"]
    ledger = results["ledger"]
    lines = [
        "# M1-D-6 v1.2.5 模型对比结果（qwen3.8-flash，no thinking，5 cases × F only）",
        "",
        f"> 状态：`{meta['status']}`；diagnostic only；无 HG repeats；不写 PASS；不计入 10 条。",
        f"> application SHA：`{meta['application_sha256']}`",
        f"> model / provider：`{meta['model']}` / `{meta['provider']}`（`{meta['base_url']}`）",
        f"> enable_thinking：`{meta['enable_thinking']}`；max_tokens：`{meta['max_tokens']}`",
        f"> ledger SHA：`{meta['ledger_sha256']}`；attempts：`{meta['ledger_total_attempts']}`；"
        f"uncertain：`{meta['ledger_uncertain_calls']}`",
        f"> 结果 JSON SHA：`{json_sha}`",
        f"> Prompt：`{meta['prompt_version']}` / frozen；rubric `{meta['rubric_version']}`；"
        f"schema `{meta['schema_version']}`",
        f"> F SHA：`{preflight['prompt_sha256']['faithfulness.txt']}`",
        f"> freeze / agent：`{meta['freeze_commit']}` / `{meta['agent_commit']}`",
        "",
        "## 0. 结论",
        "",
        f"- cases：`{meta['case_count']}`；valid=`{meta['valid_case_count']}`；"
        f"invalid=`{meta['invalid_case_count']}`。",
        f"- F status：`{meta['f_status_counts']}`；evaluated=`{meta['f_evaluated_count']}`；"
        f"invalid=`{meta['f_invalid_count']}`；skipped=`{meta['f_skipped_count']}`。",
        f"- F target hit：`{meta['f_target_hit_cases']}`；"
        f"miss：`{meta['f_target_miss_cases']}`（只观察，不改 target）。",
        f"- invalid by class：`{meta['invalid_by_class']}`",
        f"- 截断（finish_reason=length）：`{meta['truncated_cases']}`",
        f"- 与 qwen-max baseline 相比 status 变化：`{meta['baseline_status_changed_cases']}`",
        f"- 停止：`{meta['stop_triggered']}`；{meta['stop_reason'] or '—'}",
        "- **diagnostic_only；未创建 Run、未写 DB、未调 WeKnora/RAG adapter；"
        "未激活 v1.2.5；未跑正式 10/40。**",
        "",
        "## 1. 调用与计费",
        "",
        "| 项 | 实际 | 预算/上限 |",
        "|---|---:|---:|",
        f"| Judge calls | {meta['ledger_total_attempts']} | {MAX_JUDGE_CALLS} |",
        f"| input / output tokens | {ledger['input_tokens']} / {ledger['output_tokens']} | — |",
        f"| reasoning / cached tokens | {ledger['reasoning_tokens']} / "
        f"{ledger['cached_tokens']} | — |",
        f"| cost CNY（上界） | {meta['cost_cny_upper_bound']:.8f} | {CEILING_CNY:.2f} |",
        f"| ledger SHA | `{meta['ledger_sha256']}` | — |",
        f"| uncertain calls | `{meta['ledger_uncertain_calls']}` | 0 |",
        "",
        "> 计费口径：DashScope 不返回单次费用；用 qwen-max CNY 表（2.4 / 9.6 每百万）作 flash 的上界代理，实际账单更低。",
        "",
        "### 1.1 Ledger 明细",
        "",
        "| seq | case | kind | status | input | output | reasoning | finish | latency ms |",
        "|---:|---|---|---|---:|---:|---:|---|---:|",
    ]
    for row in ledger["rows"]:
        lines.append(
            f"| {row['seq']} | {row['case_id']} | {row['kind']} | {row['status']} | "
            f"{row['input_tokens']} | {row['output_tokens']} | {row['reasoning_tokens']} | "
            f"{row['finish_reason']} | {row['latency_ms']} |"
        )
    lines.extend(
        [
            "",
            "## 2. 逐 case 结果（含 baseline 对比）",
            "",
            "| case | F status | F score | target | hit | invalid class | qwen-max baseline | Δ |",
            "|---|---|---:|---|---|---|---|---:|",
        ]
    )
    for case in results["cases"]:
        f = case["metrics"]["faithfulness"]
        base = case["baseline"]
        lines.append(
            f"| {case['case_id']} | {f['status']} | {f['score']} | `{f['target']}` | "
            f"{f['target_hit']} | `{f['invalid_class']}` | "
            f"{base['status']} ({base['score']}) | {base['score_delta']} |"
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
    if meta["invalid_by_class"]:
        for name, count in sorted(meta["invalid_by_class"].items()):
            lines.append(f"| `{name}` | {count} |")
    else:
        lines.append("| — | 0 |")
    lines.extend(
        [
            "",
            "## 4. Q23 / Q35 / Q36 细节",
            "",
        ]
    )
    for case_id in ("Q23", "Q35", "Q36"):
        case = next((c for c in results["cases"] if c["case_id"] == case_id), None)
        if case is None:
            lines.extend([f"### {case_id}", "", "未运行/未收集。", ""])
            continue
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"- F：`{json.dumps(case['metrics']['faithfulness'], ensure_ascii=False)}`",
                f"- f_counts：`{json.dumps(case['f_counts'], ensure_ascii=False)}`",
                f"- initial preview：`{json.dumps(case['initial_preview'], ensure_ascii=False)}`",
                f"- patch：`{json.dumps(case['patch'], ensure_ascii=False)}`",
            ]
        )
        if case_id == "Q23":
            q23 = case.get("q23") or {}
            lines.append(
                f"- cl1 unsupported+is_contradictory：`{q23.get('cl1_unsupported_contradictory')}`；"
                f"derived=`{q23.get('derived_count')}`"
            )
        lines.append("")
    lines.extend(
        [
            "## 5. Q17 / Q21 细节",
            "",
        ]
    )
    for case_id in ("Q17", "Q21"):
        case = next((c for c in results["cases"] if c["case_id"] == case_id), None)
        if case is None:
            lines.extend([f"### {case_id}", "", "未运行/未收集。", ""])
            continue
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"- F：`{json.dumps(case['metrics']['faithfulness'], ensure_ascii=False)}`",
                f"- baseline：`{json.dumps(case['baseline'], ensure_ascii=False)}`",
                f"- f_counts：`{json.dumps(case['f_counts'], ensure_ascii=False)}`",
            ]
        )
        if case_id == "Q21":
            lines.append(
                f"- Q21 exemption：`{json.dumps(case.get('q21'), ensure_ascii=False)}`"
            )
        lines.append("")
    lines.extend(
        [
            "## 6. 停止与边界",
            "",
            f"- stop_triggered：`{meta['stop_triggered']}`",
            f"- stop_reason：{meta['stop_reason'] or '—'}",
            f"- stop_codes：`{meta['stop_codes']}`",
            f"- missing cases：`{meta['missing_cases']}`",
            "",
            "## 7. 交付声明",
            "",
            "- diagnostic only；5 cases × 1 arm × F only × 1 次；不是正式 10/40。",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora/RAG adapter。",
            "- 未激活 v1.2.5；默认仍 `v1.0.0`；未跑正式 10/40；不写 PASS。",
            "- 未修改 v1.2.5 frozen 资产/target/fixture；target v1.0.2 未改。",
            "- 只使用 flash 模型；未使用 max 模型，未使用 OpenCode/deepseek。",
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
    baseline_cases = {
        case["case_id"]: case["metrics"]["faithfulness"]
        for case in preflight_result["baseline"]["cases"]
    }
    cases: list[dict[str, Any]] = []
    effective_prompts: list[dict[str, Any]] = []
    stop_reason: str | None = None
    stop_codes: list[str] = []
    try:
        async with DashScopeFlashClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            timeout=AGENT_TIMEOUT_SECONDS + 30,
        ) as llm:
            for case_id in CASE_IDS:
                fixture_case = dataset_case(fixture, case_id)
                outcomes = await run_one(
                    recorder=recorder,
                    llm=llm,
                    fixture_case=fixture_case,
                    case_id=case_id,
                    effective_prompts=effective_prompts,
                )
                record = case_record(
                    case_id=case_id,
                    category=fixture_case.get("category") or "",
                    outcomes=outcomes,
                    recorder=recorder,
                    targets=targets_for_case(target_doc, case_id),
                    baseline=baseline_cases.get(case_id) or {},
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
                            "invalid_class": record["metrics"]["faithfulness"][
                                "invalid_class"
                            ],
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
                "f_status_counts": results["meta"]["f_status_counts"],
                "f_target_hit_cases": results["meta"]["f_target_hit_cases"],
                "f_target_miss_cases": results["meta"]["f_target_miss_cases"],
                "ledger_sha256": results["meta"]["ledger_sha256"],
                "calls": results["meta"]["ledger_total_attempts"],
                "cost_cny": results["meta"]["cost_cny_upper_bound"],
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
