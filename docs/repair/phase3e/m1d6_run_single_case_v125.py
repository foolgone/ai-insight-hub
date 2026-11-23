"""M1-D-6 v1.2.5 C single-case diagnostic runner.

- Q23 F x 3 + Q23 C/R x 1 + Q21 x 1 x 3 metrics + Q11 x 1 x 3 metrics.
- 11 primary + 5 patch + 2 reserve = 18 calls / CNY 0.40.
- judge_trace(session=None); no Run, no DB, no WeKnora/RAG adapter.
- append-only ledger at the LLM boundary.
- diagnostic_only: record invalid and continue; hard stop only on
  budget/credential/fingerprint/ledger/preflight/unprocessed.
- no PASS, not counted toward 10.

Dry-run (no LLM):
    python docs/repair/phase3e/m1d6_run_single_case_v125.py --dry-run
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import statistics
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
    PATCH_EXAMPLE_CONTEXT,
    RagJudgeAgent,
    load_judge_prompt,
)
from app.agents.structured_output import extract_json_text  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.llm import LLMClient  # noqa: E402
from app.models.rag import RagTrace  # noqa: E402
from app.schemas.agents.rag_judge_evidence import quote_validator_sha256  # noqa: E402
from app.services.rag_judge_service import judge_trace  # noqa: E402

APPLICATION_FILE = BASE / "docs/repair/phase3e/m1d6-v125-c-single-case-application.json"
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.5/MANIFEST.json"
VALIDATION_FILE = BASE / "docs/repair/phase3e/m1d7-prompt-v1.2.5-validation.json"
LEAKAGE_AUDIT_FILE = BASE / "docs/repair/phase3e/m1d7-prompt-leakage-audit.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.5"
PROMPT_DIR_V124 = BASE / "backend/app/prompts/rag_judge/v1.2.4"
PATCH_SCHEMA_FILE = BASE / "backend/app/schemas/agents/rag_judge_patch_v125.py"
LEDGER_FILE = BASE / "docs/repair/phase3e/m1d6-v125-ledger.jsonl"
OUT_JSON = BASE / "docs/repair/phase3e/m1d6-v125-results.json"
OUT_MD = BASE / "docs/repair/56-m1d6-v1.2.5-c-single-case-results.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d6-v125-results.sha256"

EXPECTED_APPLICATION_SHA = (
    "f53dd12eb9115a0688b500929620294831f338ae5841df359378a7a511be2975"
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
MAX_JUDGE_CALLS = 18
CEILING_CNY = 0.40
Q23_F_RUNS = 3
PRICE_INPUT = 0.0024 / 1000
PRICE_OUTPUT = 0.0096 / 1000
FIXED_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "m1d6:v125:user")
ABSENCE_MARKERS = ("未提及", "未说明", "未规定", "未涉及", "没有提及", "没有说明")
EXEMPTION_MARKERS = ("不受", "不适用", "除外", "例外", "仍可", "可以申请")
SPECIFIC_GOODS_MARKERS = ("定制", "生鲜", "虚拟")
PLANNED_RUNS = ("Q23-F1", "Q23-F2", "Q23-F3", "Q23-CR", "Q21", "Q11")


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

    def started_records(self) -> list[dict[str, Any]]:
        return [record for record in self.entries if record.get("event") == "started"]

    def finished_records(self) -> list[dict[str, Any]]:
        return [record for record in self.entries if record.get("event") == "finished"]

    def summary(self) -> dict[str, Any]:
        started = self.started_records()
        finished = self.finished_records()
        by_kind = Counter(str(record.get("kind") or "primary") for record in started)
        by_run = Counter(str(record.get("run_id") or "?") for record in started)
        rows: list[dict[str, Any]] = []
        finished_by_seq = {int(record["seq"]): record for record in finished}
        for record in started:
            seq = int(record["seq"])
            fin = finished_by_seq.get(seq) or {}
            usage = fin.get("usage") or {}
            rows.append(
                {
                    "seq": seq,
                    "call_id": record.get("call_id"),
                    "case_id": record.get("case_id"),
                    "run_id": record.get("run_id"),
                    "metric": record.get("metric"),
                    "kind": record.get("kind"),
                    "model_requested": record.get("model_requested"),
                    "response_model": fin.get("response_model"),
                    "temperature": record.get("temperature"),
                    "max_tokens": record.get("max_tokens"),
                    "prompt_version": record.get("prompt_version"),
                    "prompt_sha256": record.get("prompt_sha256"),
                    "system_prompt_sha256": record.get("system_prompt_sha256"),
                    "patch_claim_ids": record.get("patch_claim_ids") or [],
                    "started_at": record.get("timestamp"),
                    "finished_at": fin.get("timestamp"),
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
            "started_by_kind": dict(by_kind),
            "started_by_run": dict(by_run),
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

    def for_run(self, run_id: str, metric: str | None = None) -> list[dict[str, Any]]:
        return [
            call
            for call in self.calls
            if call["run_id"] == run_id and (metric is None or call["metric"] == metric)
        ]

    def summary_for_run(self, run_id: str) -> dict[str, Any]:
        calls = self.for_run(run_id)
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


def synthetic_trace(case: dict[str, Any], run_id: str) -> RagTrace:
    case_id = case["id"]
    return RagTrace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"m1d6:v125:{case_id}:{run_id}"),
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
        "faithfulness_strict": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
    }
    for outcome in outcomes:
        config = outcome.judge_config or {}
        if config.get("prompt_version") != PROMPT_VERSION:
            errors.append(
                f"{outcome.metric_name}: prompt_version={config.get('prompt_version')!r}"
            )
        if config.get("schema_version") != SCHEMA_VERSION:
            errors.append(
                f"{outcome.metric_name}: schema_version={config.get('schema_version')!r}"
            )
        if config.get("metric_version") != METRIC_VERSION:
            errors.append(
                f"{outcome.metric_name}: metric_version={config.get('metric_version')!r}"
            )
        if config.get("rubric_version") != RUBRIC_VERSION:
            errors.append(
                f"{outcome.metric_name}: rubric_version={config.get('rubric_version')!r}"
            )
        if config.get("temperature") not in (0.0, 0):
            errors.append(
                f"{outcome.metric_name}: temperature={config.get('temperature')!r}"
            )
        if config.get("max_tokens") != 8192:
            errors.append(
                f"{outcome.metric_name}: max_tokens={config.get('max_tokens')!r}"
            )
        if config.get("model") not in (None, "qwen-max"):
            errors.append(f"{outcome.metric_name}: model={config.get('model')!r}")
        if outcome.metric_name in {"faithfulness", "faithfulness_strict"}:
            if config.get("contract_repair_version") != PROMPT_VERSION:
                errors.append(
                    f"{outcome.metric_name}: "
                    f"contract_repair_version={config.get('contract_repair_version')!r}"
                )
            if config.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
                errors.append(
                    f"{outcome.metric_name}: "
                    f"quote_validator_sha256={config.get('quote_validator_sha256')!r}"
                )
        expected_sha = expected.get(outcome.metric_name)
        if expected_sha and config.get("prompt_sha256") != expected_sha:
            errors.append(
                f"{outcome.metric_name}: prompt_sha256={config.get('prompt_sha256')!r}"
            )
    return errors


def validate_ledger_run(ledger: LedgerWriter, run_id: str) -> list[str]:
    expected = {
        "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
    }
    errors: list[str] = []
    for record in ledger.started_records():
        if record.get("run_id") != run_id:
            continue
        if record.get("kind") not in {"primary", "retry"}:
            continue
        metric = str(record.get("metric") or "")
        expected_sha = expected.get(metric)
        if expected_sha and record.get("system_prompt_sha256") != expected_sha:
            errors.append(
                f"{run_id}/{metric}/{record.get('kind')}: "
                f"system_prompt_sha256={record.get('system_prompt_sha256')!r}"
            )
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


def claim_effective_id(claim: dict[str, Any], index: int) -> str:
    return str(claim.get("claim_id") or f"cl{index}")


def initial_id_mapping(initial_output: str | None) -> list[dict[str, Any]]:
    if not initial_output:
        return []
    try:
        payload = json.loads(extract_json_text(initial_output))
        claims = list(payload.get("claims") or [])
    except (TypeError, ValueError):
        return []
    return [
        {
            "index": index,
            "raw_claim_id": claim.get("claim_id"),
            "effective_claim_id": claim_effective_id(claim, index),
        }
        for index, claim in enumerate(claims, 1)
    ]


def q23_run_record(
    *,
    run_id: str,
    outcomes: list[Any],
    recorder: CallRecorder,
    ledger_errors: list[str],
) -> dict[str, Any]:
    outcomes_by_name = by_metric(outcomes)
    f = outcomes_by_name.get("faithfulness")
    strict = outcomes_by_name.get("faithfulness_strict")
    details = getattr(f, "details", {}) or {}
    contract = details.get("agent_contract") or {}
    claims = list(details.get("claims") or [])
    calls = recorder.for_run(run_id, "faithfulness")
    primary = next(
        (
            call
            for call in reversed(calls)
            if call["kind"] in {"primary", "retry"} and call.get("content")
        ),
        None,
    )
    patch = next(
        (
            call
            for call in reversed(calls)
            if call["kind"] == "patch" and call.get("content")
        ),
        None,
    )
    initial_output = primary.get("content") if primary else None
    patch_output = patch.get("content") if patch else None
    merged_output = getattr(f, "raw_output", None)
    cl1 = next((claim for claim in claims if claim.get("claim_id") == "cl1"), None)
    derived = [
        {
            "claim_id": claim.get("claim_id"),
            "claim": claim.get("claim"),
            "support_status": claim.get("support_status"),
            "quotes": [
                str(ref.get("quote") or "")
                for ref in (claim.get("evidence_refs") or [])
            ],
        }
        for claim in claims
        if claim.get("claim_subtype") == "derived"
    ]
    insufficient = [
        claim
        for claim in claims
        if claim.get("claim_type") == "factual_claim"
        and claim.get("support_status") == "insufficient_evidence"
    ]
    derived_supported = [
        claim for claim in derived if claim.get("support_status") == "supported"
    ]
    premise_markers = ("第2天", "第 2 天", "超过24小时", "超过 24 小时")
    conclusion_markers = ("已超出", "不符合")
    premise_insufficient_conclusion_supported = any(
        any(
            marker in normalized(claim.get("claim") or "") for marker in premise_markers
        )
        for claim in insufficient
    ) and any(
        any(
            marker in normalized(claim.get("claim") or "")
            for marker in conclusion_markers
        )
        for claim in derived_supported
    )
    patch_info = {
        "triggered": bool(contract.get("repair_triggered")),
        "applied_claims": list(contract.get("patch_applied_claims") or []),
        "refusal": contract.get("patch_refusal"),
        "unsupported_quote_claims": list(
            contract.get("patch_unsupported_quote_claims") or []
        ),
        "expected_claims": list(contract.get("patch_expected_claims") or []),
        "provided_claims": list(contract.get("patch_provided_claims") or []),
        "missing_claims": list(contract.get("patch_missing_claims") or []),
        "final_errors": list(contract.get("final_errors") or []),
        "example_quote_copied": bool(
            patch_output and PATCH_EXAMPLE_CONTEXT in patch_output
        ),
        "merged_output_present": bool(merged_output),
    }
    return {
        "run_id": run_id,
        "case_id": "Q23",
        "f_status": getattr(f, "status", None),
        "f_score": getattr(f, "score", None),
        "f_invalid_reason": getattr(f, "invalid_reason", None),
        "f_strict_status": getattr(strict, "status", None),
        "f_strict_score": getattr(strict, "score", None),
        "counts": {
            key: details.get(key)
            for key in (
                "claim_count",
                "supported_count",
                "unsupported_count",
                "insufficient_evidence_count",
                "non_factual_count",
                "scorable_claim_count",
            )
        },
        "target": [0.4, 0.5],
        "target_hit": in_target(getattr(f, "score", None), [0.4, 0.5]),
        "claims": claims,
        "cl1": cl1,
        "derived_claims": derived,
        "derived_count": len(derived),
        "premise_insufficient_conclusion_supported": (
            premise_insufficient_conclusion_supported
        ),
        "effective_id_mapping": initial_id_mapping(initial_output),
        "patch": patch_info,
        "initial_output": initial_output,
        "patch_output": patch_output,
        "merged_output": merged_output,
        "agent_contract": contract,
        "validation_errors": details.get("validation_errors") or [],
        "mixed_sentence_warnings": list(contract.get("mixed_sentence_warnings") or []),
        "absence_fields": [
            {
                "claim_id": claim.get("claim_id"),
                "claim": claim.get("claim"),
                "claim_type": claim.get("claim_type"),
                "claim_subtype": claim.get("claim_subtype"),
                "support_status": claim.get("support_status"),
                "evidence_refs": claim.get("evidence_refs") or [],
            }
            for claim in claims
            if claim.get("claim_subtype") == "absence"
        ],
        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
        "fingerprint_errors": validate_fingerprint(outcomes) + ledger_errors,
        "credential_failure": any(
            outcome.details.get("failure_kind") == "credential"
            or str(outcome.error_type or "").startswith("LLMCredential")
            for outcome in outcomes
        ),
        "call_summary": recorder.summary_for_run(run_id),
    }


def q23_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    valid_scores = [
        float(run["f_score"])
        for run in runs
        if run.get("f_status") == "evaluated" and run.get("f_score") is not None
    ]
    invalid_runs = [
        run["run_id"]
        for run in runs
        if run.get("f_status") != "evaluated" or run.get("f_score") is None
    ]
    median = statistics.median(valid_scores) if len(valid_scores) >= 2 else None
    target_hit_count = sum(1 for score in valid_scores if 0.4 <= score <= 0.5)
    return {
        "runs": len(runs),
        "valid_scores": valid_scores,
        "valid_run_count": len(valid_scores),
        "invalid_runs": invalid_runs,
        "invalid_run_count": len(invalid_runs),
        "median": median,
        "min": min(valid_scores) if valid_scores else None,
        "max": max(valid_scores) if valid_scores else None,
        "target_hit_count": target_hit_count,
        "target_hit_rate": (
            round(target_hit_count / len(valid_scores), 6) if valid_scores else None
        ),
        "median_in_target": (bool(median is not None and 0.4 <= median <= 0.5)),
        "insufficient_valid_runs": len(valid_scores) < 2,
        "all_runs_completed": len(runs) == Q23_F_RUNS,
    }


def q23_cr_record(
    *, run_id: str, outcomes: list[Any], recorder: CallRecorder
) -> dict[str, Any]:
    outcomes_by_name = by_metric(outcomes)
    c = outcomes_by_name.get("answer_correctness")
    r = outcomes_by_name.get("answer_relevancy")
    c_contract = (getattr(c, "details", {}) or {}).get("agent_contract") or {}
    return {
        "run_id": run_id,
        "case_id": "Q23",
        "c_status": getattr(c, "status", None),
        "c_score": getattr(c, "score", None),
        "c_target": [0.0, 0.2],
        "c_target_hit": in_target(getattr(c, "score", None), [0.0, 0.2]),
        "c_warning": c_contract.get("correctness_first_sentence_warning"),
        "r_status": getattr(r, "status", None),
        "r_score": getattr(r, "score", None),
        "r_target": [0.7, 1.0],
        "r_target_hit": in_target(getattr(r, "score", None), [0.7, 1.0]),
        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
        "fingerprint_errors": validate_fingerprint(outcomes),
        "call_summary": recorder.summary_for_run(run_id),
        "snapshot_only": True,
    }


def q21_record(
    *, run_id: str, outcomes: list[Any], recorder: CallRecorder
) -> dict[str, Any]:
    outcomes_by_name = by_metric(outcomes)
    f = outcomes_by_name.get("faithfulness")
    c = outcomes_by_name.get("answer_correctness")
    r = outcomes_by_name.get("answer_relevancy")
    details = getattr(f, "details", {}) or {}
    claims = list(details.get("claims") or [])
    exemption_claims: list[dict[str, Any]] = []
    for claim in claims:
        text = normalized(claim.get("claim") or "")
        if "质量问题" not in text:
            continue
        if not any(marker in text for marker in ("7天", "七天", "限制")):
            continue
        quotes = [
            str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])
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
    return {
        "run_id": run_id,
        "case_id": "Q21",
        "metrics": {
            "faithfulness": {
                "status": getattr(f, "status", None),
                "score": getattr(f, "score", None),
                "target": [0.6, 0.7],
                "target_hit": in_target(getattr(f, "score", None), [0.6, 0.7]),
            },
            "answer_correctness": {
                "status": getattr(c, "status", None),
                "score": getattr(c, "score", None),
                "target": None,
                "target_hit": None,
            },
            "answer_relevancy": {
                "status": getattr(r, "status", None),
                "score": getattr(r, "score", None),
                "target": None,
                "target_hit": None,
            },
        },
        "f_target_hit": in_target(getattr(f, "score", None), [0.6, 0.7]),
        "exemption_claims": exemption_claims,
        "forbidden_quote": any(item["forbidden_quote"] for item in exemption_claims),
        "claims": claims,
        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
        "fingerprint_errors": validate_fingerprint(outcomes),
        "call_summary": recorder.summary_for_run(run_id),
    }


def q11_record(
    *,
    run_id: str,
    outcomes: list[Any],
    recorder: CallRecorder,
    contexts: list[str],
) -> dict[str, Any]:
    outcomes_by_name = by_metric(outcomes)
    f = outcomes_by_name.get("faithfulness")
    c = outcomes_by_name.get("answer_correctness")
    r = outcomes_by_name.get("answer_relevancy")
    details = getattr(f, "details", {}) or {}
    claims = list(details.get("claims") or [])
    quote_checks: list[dict[str, Any]] = []
    for claim in claims:
        for ref in claim.get("evidence_refs") or []:
            quote = str(ref.get("quote") or "")
            found = any(quote and quote in context for context in contexts)
            quote_checks.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "context_id": ref.get("context_id"),
                    "quote": quote,
                    "contiguous_substring": found,
                    "has_ellipsis": "?" in quote or "..." in quote,
                }
            )
    return {
        "run_id": run_id,
        "case_id": "Q11",
        "metrics": {
            "faithfulness": {
                "status": getattr(f, "status", None),
                "score": getattr(f, "score", None),
                "target": [0.6, 0.9],
                "target_hit": in_target(getattr(f, "score", None), [0.6, 0.9]),
            },
            "answer_correctness": {
                "status": getattr(c, "status", None),
                "score": getattr(c, "score", None),
                "target": [0.8, 1.0],
                "target_hit": in_target(getattr(c, "score", None), [0.8, 1.0]),
            },
            "answer_relevancy": {
                "status": getattr(r, "status", None),
                "score": getattr(r, "score", None),
                "target": [0.9, 1.0],
                "target_hit": in_target(getattr(r, "score", None), [0.9, 1.0]),
            },
        },
        "claims": claims,
        "quote_checks": quote_checks,
        "contexts_count": len(contexts),
        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
        "fingerprint_errors": validate_fingerprint(outcomes),
        "call_summary": recorder.summary_for_run(run_id),
    }


def call_matrix() -> dict[str, Any]:
    segments = [
        {"segment": "Q23 F x 3", "primary": 3, "patch": 3},
        {"segment": "Q23 C / R", "primary": 2, "patch": 0},
        {"segment": "Q21", "primary": 3, "patch": 1},
        {"segment": "Q11", "primary": 3, "patch": 1},
    ]
    return {
        "segments": segments,
        "primary": 11,
        "patch": 5,
        "shared_reserve": 2,
        "max_judge_calls": MAX_JUDGE_CALLS,
        "ceiling_cny": CEILING_CNY,
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
    agent_diff = run_command(
        "diff",
        "--quiet",
        EXPECTED_AGENT_COMMIT,
        "--",
        "backend/app/agents/rag_judge_agent.py",
    )
    errors: list[str] = []
    if head.returncode != 0:
        errors.append(f"git head={head.returncode}")
    if frozen_diff.returncode != 0:
        errors.append(
            "frozen_assets_diff="
            f"{frozen_diff.returncode}: {frozen_diff.stderr.strip()}"
        )
    if agent_diff.returncode != 0:
        errors.append(
            f"agent_diff={agent_diff.returncode}: {agent_diff.stderr.strip()}"
        )
    for name, result in commits.items():
        if result.returncode != 0:
            errors.append(f"{name}_commit={result.returncode}")
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "commits_present": {
            name: result.returncode == 0 for name, result in commits.items()
        },
        "frozen_assets_unchanged_since_freeze": frozen_diff.returncode == 0,
        "agent_unchanged_since_agent_commit": agent_diff.returncode == 0,
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
        "scope": "c_single_case_diagnostic",
        "case_count": 3,
        "q23_f_runs": 3,
        "q23_cr_runs": 1,
        "q21_runs": 1,
        "q11_runs": 1,
        "not_approved_for_10_or_40": True,
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
        "ledger_file": "docs/repair/phase3e/m1d6-v125-ledger.jsonl",
        "ledger_initial_sha256": EXPECTED_LEDGER_INITIAL_SHA,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            errors.append(f"application meta.{key}={meta.get(key)!r} != {expected!r}")
    if meta.get("prompt_sha256") != EXPECTED_PROMPT_SHA:
        errors.append("application prompt_sha256 mismatch")
    if meta.get("leakage_findings") != 0:
        errors.append("application leakage_findings != 0")
    if run_config.get("judge_prompt_version") != PROMPT_VERSION:
        errors.append("application judge_prompt_version mismatch")
    if run_config.get("default_prompt_version") != DEFAULT_PROMPT_VERSION:
        errors.append("application default_prompt_version mismatch")
    if run_config.get("q23_f_runs") != 3 or run_config.get("q23_cr_runs") != 1:
        errors.append("application Q23 runs mismatch")
    if run_config.get("q21_runs") != 1 or run_config.get("q11_runs") != 1:
        errors.append("application Q21/Q11 runs mismatch")
    if run_config.get("session") is not None:
        errors.append("application session is not null")
    service_path = run_config.get("service_path") or {}
    if service_path.get("creates_run") is not False:
        errors.append("application creates_run is not false")
    if service_path.get("writes_db") is not False:
        errors.append("application writes_db is not false")
    for key in ("no_rag_call", "no_platform_run", "no_db_write", "no_weknora_call"):
        if run_config.get(key) is not True:
            errors.append(f"application {key} is not true")
    if budget.get("primary_judge_calls") != 11:
        errors.append(
            f"application primary_judge_calls={budget.get('primary_judge_calls')!r}"
        )
    if budget.get("patch_reserve") != 5:
        errors.append(f"application patch_reserve={budget.get('patch_reserve')!r}")
    if budget.get("retry_repair_reserve") != 2:
        errors.append(
            f"application retry_repair_reserve={budget.get('retry_repair_reserve')!r}"
        )
    if budget.get("max_judge_calls") != MAX_JUDGE_CALLS:
        errors.append(f"application max_judge_calls={budget.get('max_judge_calls')!r}")
    if budget.get("ceiling_cny") != CEILING_CNY:
        errors.append(f"application ceiling_cny={budget.get('ceiling_cny')!r}")
    case_ids = [case.get("case_id") for case in cases]
    if case_ids != ["Q23", "Q21", "Q11"]:
        errors.append(f"application case_ids={case_ids!r}")
    return errors


def manifest_checks(manifest: dict[str, Any], validation: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("version") != PROMPT_VERSION:
        errors.append(f"manifest version={manifest.get('version')!r}")
    if manifest.get("status") != "frozen" or manifest.get("frozen") is not True:
        errors.append("manifest is not frozen")
    if manifest.get("active") is not False:
        errors.append("manifest active is not false")
    if manifest.get("runtime_active") is not False:
        errors.append("manifest runtime_active is not false")
    if manifest.get("default_prompt_version") != DEFAULT_PROMPT_VERSION:
        errors.append("manifest default_prompt_version mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest schema_version={manifest.get('schema_version')!r}")
    if manifest.get("rubric_version") != RUBRIC_VERSION:
        errors.append(f"manifest rubric_version={manifest.get('rubric_version')!r}")
    if manifest.get("prompts") != EXPECTED_PROMPT_SHA:
        errors.append("manifest prompts SHA mismatch")
    if manifest.get("patch_schema_sha256") != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append("manifest patch_schema_sha256 mismatch")
    if manifest.get("patch_example_sha256") != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append("manifest patch_example_sha256 mismatch")
    if manifest.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append("manifest quote_validator_sha256 mismatch")
    leakage = manifest.get("leakage_audit") or {}
    if leakage.get("findings") != 0:
        errors.append(f"manifest leakage findings={leakage.get('findings')!r}")
    if validation.get("status") != "pass":
        errors.append(f"validation status={validation.get('status')!r}")
    if validation.get("prompt_version") != PROMPT_VERSION:
        errors.append(f"validation prompt_version={validation.get('prompt_version')!r}")
    if validation.get("manifest_sha256") != EXPECTED_MANIFEST_SHA:
        errors.append("validation manifest_sha256 mismatch")
    if validation.get("patch_schema_sha256") != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append("validation patch_schema_sha256 mismatch")
    if validation.get("patch_example_sha256") != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append("validation patch_example_sha256 mismatch")
    if validation.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append("validation quote_validator_sha256 mismatch")
    failed = [
        check.get("check")
        for check in validation.get("checks") or []
        if not check.get("ok")
    ]
    if failed:
        errors.append(f"validation failed checks: {failed}")
    if len(validation.get("checks") or []) != 28:
        errors.append(f"validation check_count={len(validation.get('checks') or [])}")
    return errors


def budget_self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="m1d6-v125-budget-") as tmp:
        ledger_path = Path(tmp) / "ledger.jsonl"
        ledger_path.write_bytes(b"")
        ledger = LedgerWriter(
            ledger_path,
            EXPECTED_LEDGER_INITIAL_SHA,
            require_empty=True,
        )
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
                run_id="R19",
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
        errors: list[str] = []
        if ledger.attempts != MAX_JUDGE_CALLS:
            errors.append(f"attempts={ledger.attempts}")
        if ledger.uncertain_calls != 0:
            errors.append(f"uncertain_calls={ledger.uncertain_calls}")
        if not rejected:
            errors.append("19th call was not rejected")
        return {
            "ok": not errors,
            "errors": errors,
            "attempts": ledger.attempts,
            "finished_calls": ledger.finished_calls,
            "uncertain_calls": ledger.uncertain_calls,
            "nineteenth_rejected": rejected,
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
    prompt_sha_v124 = {
        name: sha256_bytes((PROMPT_DIR_V124 / name).read_bytes())
        for name in ("answer_correctness.txt", "answer_relevancy.txt")
    }
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=PROMPT_VERSION)
    patch_example = agent._patch_example_v125() or ""
    patch_example_sha = sha256_text(patch_example)
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
        errors.append(f"fixture_sha={fixture_sha}")
    if target_sha != EXPECTED_TARGET_SHA:
        errors.append(f"target_sha={target_sha}")
    if labels_sha != EXPECTED_LABELS_SHA:
        errors.append(f"labels_sha={labels_sha}")
    if manifest_sha != EXPECTED_MANIFEST_SHA:
        errors.append(f"manifest_sha={manifest_sha}")
    if validation_sha != EXPECTED_VALIDATION_SHA:
        errors.append(f"validation_sha={validation_sha}")
    if leakage_sha != EXPECTED_LEAKAGE_AUDIT_SHA:
        errors.append(f"leakage_sha={leakage_sha}")
    if patch_schema_sha != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append(f"patch_schema_sha={patch_schema_sha}")
    if patch_example_sha != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append(f"patch_example_sha={patch_example_sha}")
    if quote_sha != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append(f"quote_validator_sha={quote_sha}")
    if prompt_sha != EXPECTED_PROMPT_SHA:
        errors.append(f"prompt_sha={prompt_sha}")
    if (
        prompt_sha_v124["answer_correctness.txt"]
        != EXPECTED_PROMPT_SHA["answer_correctness.txt"]
    ):
        errors.append("v1.2.4 C prompt SHA mismatch")
    if (
        prompt_sha_v124["answer_relevancy.txt"]
        != EXPECTED_PROMPT_SHA["answer_relevancy.txt"]
    ):
        errors.append("v1.2.4 R prompt SHA mismatch")
    if ledger_sha != EXPECTED_LEDGER_INITIAL_SHA:
        errors.append(f"ledger_initial_sha={ledger_sha}")
    if ledger_bytes:
        errors.append(f"ledger is not empty: bytes={len(ledger_bytes)}")
    if not budget_test["ok"]:
        errors.append(f"budget_self_test={budget_test['errors']}")
    if leakage.get("status") != "pass" or leakage.get("finding_count") != 0:
        errors.append(
            "leakage audit is not pass/0: "
            f"status={leakage.get('status')!r}, "
            f"findings={leakage.get('finding_count')!r}"
        )
    errors.extend(application_checks(application))
    errors.extend(manifest_checks(manifest, validation))
    errors.extend(git["errors"])
    if settings.DEFAULT_LLM_MODEL != "qwen-max":
        errors.append(f"model={settings.DEFAULT_LLM_MODEL!r}")
    if settings.DEFAULT_TEMPERATURE != 0.0:
        errors.append(f"temperature={settings.DEFAULT_TEMPERATURE!r}")
    if settings.RAG_JUDGE_MAX_TOKENS != 8192:
        errors.append(f"max_tokens={settings.RAG_JUDGE_MAX_TOKENS!r}")
    if settings.RAG_JUDGE_PROMPT_VERSION != DEFAULT_PROMPT_VERSION:
        errors.append(f"default_prompt_version={settings.RAG_JUDGE_PROMPT_VERSION!r}")
    fixture_cases = {case["id"]: case for case in fixture.get("cases") or []}
    for case_id in ("Q23", "Q21", "Q11"):
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
        "agent_unchanged_since_agent_commit": git["agent_unchanged_since_agent_commit"],
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


def dry_run_payload(preflight_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "ok": not preflight_result["errors"],
        "errors": preflight_result["errors"],
        "application_sha256": preflight_result["application_sha256"],
        "prompt_version": PROMPT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "f_sha256": preflight_result["prompt_sha256"]["faithfulness.txt"],
        "c_sha256": preflight_result["prompt_sha256"]["answer_correctness.txt"],
        "r_sha256": preflight_result["prompt_sha256"]["answer_relevancy.txt"],
        "patch_schema_sha256": preflight_result["patch_schema_sha256"],
        "patch_example_sha256": preflight_result["patch_example_sha256"],
        "quote_validator_sha256": preflight_result["quote_validator_sha256"],
        "manifest_sha256": preflight_result["manifest_sha256"],
        "validation_sha256": preflight_result["validation_sha256"],
        "leakage_audit_sha256": preflight_result["leakage_audit_sha256"],
        "leakage_findings": preflight_result["leakage_findings"],
        "fixture_sha256": preflight_result["fixture_sha256"],
        "target_sha256": preflight_result["target_sha256"],
        "labels_sha256": preflight_result["labels_sha256"],
        "freeze_commit": preflight_result["freeze_commit"],
        "agent_commit": preflight_result["agent_commit"],
        "git_head": preflight_result["git_head"],
        "frozen_assets_unchanged_since_freeze": preflight_result[
            "frozen_assets_unchanged_since_freeze"
        ],
        "agent_unchanged_since_agent_commit": preflight_result[
            "agent_unchanged_since_agent_commit"
        ],
        "ledger_file": preflight_result["ledger_file"],
        "ledger_initial_sha256": preflight_result["ledger_initial_sha256"],
        "ledger_empty": preflight_result["ledger_empty"],
        "budget": preflight_result["call_matrix"],
        "budget_self_test": preflight_result["budget_self_test"],
        "call_matrix": preflight_result["call_matrix"]["segments"],
        "llm_calls": 0,
        "judge_runs": 0,
    }


async def run_one(
    *,
    recorder: CallRecorder,
    real_llm: LLMClient,
    fixture_case: dict[str, Any],
    case_id: str,
    run_id: str,
    metrics: list[str] | None,
    effective_prompts: list[dict[str, Any]],
) -> list[Any]:
    context = {"case_id": case_id, "run_id": run_id}

    def factory(metric: str) -> RagJudgeAgent:
        loaded = load_judge_prompt(PROMPT_VERSION, metric)
        loaded_sha = sha256_text(loaded)
        expected_sha = EXPECTED_PROMPT_SHA[f"{metric}.txt"]
        effective_prompts.append(
            {
                "run_id": run_id,
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
        trace=synthetic_trace(fixture_case, run_id),
        item=SimpleNamespace(gold_answer=fixture_case["gold_answer"]),
        metrics=metrics,
        prompt_version=PROMPT_VERSION,
        agent_factory=factory,
    )


def check_hard_stop(
    *,
    recorder: CallRecorder,
    ledger: LedgerWriter,
    runs: list[dict[str, Any]],
    run_id: str,
    fingerprint_errors: list[str],
    credential_failure: bool,
    ledger_errors: list[str],
) -> tuple[str | None, list[str]]:
    if recorder.budget_exceeded or ledger.budget_error:
        return "budget_ceiling", ["budget_ceiling"]
    if credential_failure:
        return "credential_failure", ["credential_failure"]
    if fingerprint_errors:
        return "fingerprint_mismatch", ["fingerprint_mismatch"]
    if ledger_errors:
        return "ledger_integrity", ["ledger_integrity"]
    if ledger.uncertain_calls:
        return "ledger_integrity", ["ledger_integrity"]
    return None, []


def dataset_case(fixture: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(case for case in fixture["cases"] if case["id"] == case_id)


def build_results(
    *,
    preflight_result: dict[str, Any],
    recorder: CallRecorder,
    ledger: LedgerWriter,
    q23_runs: list[dict[str, Any]],
    q23_cr: dict[str, Any] | None,
    q21: dict[str, Any] | None,
    q11: dict[str, Any] | None,
    effective_prompts: list[dict[str, Any]],
    stop_reason: str | None,
    stop_codes: list[str],
) -> dict[str, Any]:
    q23 = q23_summary(q23_runs)
    completed_runs = [run["run_id"] for run in q23_runs]
    if q23_cr:
        completed_runs.append(q23_cr["run_id"])
    if q21:
        completed_runs.append(q21["run_id"])
    if q11:
        completed_runs.append(q11["run_id"])
    missing_runs = [run_id for run_id in PLANNED_RUNS if run_id not in completed_runs]
    status = "stopped" if stop_reason else "collected"
    if not stop_reason and missing_runs:
        status = "stopped"
        stop_reason = f"unprocessed runs: {missing_runs}"
        stop_codes = ["unprocessed_case"]
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
    results = {
        "meta": {
            "name": "m1d6-v1.2.5-c-single-case-results",
            "status": status,
            "diagnostic_only": True,
            "counts_toward_10": False,
            "pass_written": False,
            "date": "2026-11-23",
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
            "ran_10": False,
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
            "q23_f_median": q23["median"],
            "q23_f_min": q23["min"],
            "q23_f_max": q23["max"],
            "q23_f_valid_runs": q23["valid_run_count"],
            "q23_f_invalid_runs": q23["invalid_runs"],
            "q23_f_target_hit_count": q23["target_hit_count"],
            "q23_f_target_hit_rate": q23["target_hit_rate"],
            "q23_f_median_in_target": q23["median_in_target"],
            "q23_f_insufficient_valid_runs": q23["insufficient_valid_runs"],
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
        "q23": {
            "runs": q23_runs,
            "summary": q23,
            "c_r_snapshot": q23_cr,
        },
        "q21": q21,
        "q11": q11,
        "ledger": ledger_summary,
        "completed_runs": completed_runs,
        "missing_runs": missing_runs,
    }
    return results


def render_metric_table(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "| metric | status | score | target | target hit |",
        "|---|---|---:|---|---|",
    ]
    for name, payload in metrics.items():
        lines.append(
            f"| {name} | {payload.get('status')} | {payload.get('score')} | "
            f"`{payload.get('target')}` | {payload.get('target_hit')} |"
        )
    return lines


def render_q23_run(run: dict[str, Any]) -> list[str]:
    patch = run.get("patch") or {}
    lines = [
        f"### {run['run_id']}",
        "",
        f"- F：`{run.get('f_status')}` / score=`{run.get('f_score')}` / "
        f"target hit=`{run.get('target_hit')}`",
        f"- F_strict：`{run.get('f_strict_status')}` / "
        f"score=`{run.get('f_strict_score')}`",
        f"- counts：`{json.dumps(run.get('counts'), ensure_ascii=False)}`",
        f"- derived_count：`{run.get('derived_count')}`；"
        f"premise-insufficient + conclusion-supported："
        f"`{run.get('premise_insufficient_conclusion_supported')}`",
        f"- patch：triggered=`{patch.get('triggered')}`；"
        f"applied=`{patch.get('applied_claims')}`；"
        f"refusal=`{patch.get('refusal')}`；"
        f"missing=`{patch.get('missing_claims')}`；"
        f"unsupported_quote_claims=`{patch.get('unsupported_quote_claims')}`；"
        f"example_copied=`{patch.get('example_quote_copied')}`",
        f"- fingerprint_errors：`{run.get('fingerprint_errors')}`",
        f"- call summary：`{json.dumps(run.get('call_summary'), ensure_ascii=False)}`",
        "",
        "cl1：",
        "",
        "```json",
        json.dumps(run.get("cl1"), ensure_ascii=False, indent=1),
        "```",
        "",
        "derived claims：",
        "",
        "```json",
        json.dumps(run.get("derived_claims"), ensure_ascii=False, indent=1),
        "```",
        "",
        "effective claim_id mapping：",
        "",
        "```json",
        json.dumps(run.get("effective_id_mapping"), ensure_ascii=False, indent=1),
        "```",
        "",
        "absence fields：",
        "",
        "```json",
        json.dumps(run.get("absence_fields"), ensure_ascii=False, indent=1),
        "```",
        "",
    ]
    return lines


def write_report(results: dict[str, Any], json_sha: str) -> str:
    meta = results["meta"]
    q23 = results["q23"]
    q23_summary_data = q23["summary"]
    q23_cr = q23["c_r_snapshot"]
    q21 = results["q21"]
    q11 = results["q11"]
    ledger = results["ledger"]
    lines = [
        "# M1-D-6 v1.2.5 C 单案例诊断结果（Q23 F×3 + Q21/Q11）",
        "",
        f"> 状态：`{meta['status']}`；diagnostic only；不写 PASS；不计入 10 条。",
        f"> application SHA：`{meta['application_sha256']}`",
        f"> ledger SHA：`{meta['ledger_sha256']}`；"
        f"total attempts：`{meta['ledger_total_attempts']}`；"
        f"uncertain calls：`{meta['ledger_uncertain_calls']}`",
        f"> 结果 JSON SHA：`{json_sha}`",
        f"> Prompt：`{meta['prompt_version']}` / `frozen` / "
        f"rubric `{meta['rubric_version']}` / schema `{meta['schema_version']}` / "
        f"metric `{meta['metric_version']}`",
        f"> F / C / R：`{meta['preflight']['prompt_sha256']['faithfulness.txt']}` / "
        f"`{meta['preflight']['prompt_sha256']['answer_correctness.txt']}` / "
        f"`{meta['preflight']['prompt_sha256']['answer_relevancy.txt']}`",
        f"> MANIFEST / validation / leakage：`{meta['manifest_sha256']}` / "
        f"`{meta['validation_sha256']}` / `{meta['leakage_audit_sha256']}`",
        f"> patch schema / example / validator：`{meta['patch_schema_sha256']}` / "
        f"`{meta['patch_example_sha256']}` / `{meta['quote_validator_sha256']}`",
        f"> agent / freeze / test / report / design：`{meta['agent_commit']}` / "
        f"`{meta['freeze_commit']}` / `{meta['test_fix_commit']}` / "
        f"`{meta['implementation_report_commit']}` / `{meta['design_commit']}`",
        "",
        "## 0. 结论",
        "",
        f"- Q23 F runs：valid=`{q23_summary_data['valid_run_count']}`；"
        f"invalid=`{q23_summary_data['invalid_run_count']}`；"
        f"median=`{q23_summary_data['median']}`；"
        f"min=`{q23_summary_data['min']}`；max=`{q23_summary_data['max']}`；"
        f"target hit count=`{q23_summary_data['target_hit_count']}`；"
        f"median in target=`{q23_summary_data['median_in_target']}`。",
        f"- Q23 C/R snapshot：C=`{q23_cr.get('c_score') if q23_cr else None}`；"
        f"R=`{q23_cr.get('r_score') if q23_cr else None}`；"
        "仅作 snapshot，不宣称稳定。",
        f"- Q21：`{json.dumps(q21.get('metrics') if q21 else None, ensure_ascii=False)}`",
        f"- Q11：`{json.dumps(q11.get('metrics') if q11 else None, ensure_ascii=False)}`",
        f"- 停止：`{meta['stop_triggered']}`；{meta['stop_reason'] or '—'}",
        "- **diagnostic_only；未创建 Run、未写 DB、未调 WeKnora/RAG adapter；"
        "未激活 v1.2.5；未跑 10/40。**",
        "",
        "## 1. 运行时指纹",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| prompt / rubric | `{meta['prompt_version']}` / `{meta['rubric_version']}` |",
        f"| F / C / R | `{meta['preflight']['prompt_sha256']['faithfulness.txt']}` / "
        f"`{meta['preflight']['prompt_sha256']['answer_correctness.txt']}` / "
        f"`{meta['preflight']['prompt_sha256']['answer_relevancy.txt']}` |",
        f"| MANIFEST / validation | `{meta['manifest_sha256']}` / "
        f"`{meta['validation_sha256']}` |",
        f"| patch schema / example | `{meta['patch_schema_sha256']}` / "
        f"`{meta['patch_example_sha256']}` |",
        f"| quote validator | `{meta['quote_validator_sha256']}` |",
        f"| leakage audit | `{meta['leakage_audit_sha256']}`；"
        f"findings={meta['leakage_findings']} |",
        f"| fixture / target / labels | `{meta['fixture_sha256']}` / "
        f"`{meta['target_sha256']}` / `{meta['labels_sha256']}` |",
        f"| default / active | `{meta['default_prompt_version']}` / "
        f"`{meta['prompt_active']}` |",
        "",
        "## 2. 调用与 Ledger",
        "",
        "| 项 | 实际 | 预算/上限 |",
        "|---|---:|---:|",
        f"| Judge calls（ledger attempts） | {meta['ledger_total_attempts']} | "
        f"{MAX_JUDGE_CALLS} |",
        f"| input / output tokens | {ledger['input_tokens']} / "
        f"{ledger['output_tokens']} | — |",
        f"| cost CNY | {meta['cost_cny']:.8f} | {CEILING_CNY:.2f} |",
        f"| ledger SHA | `{meta['ledger_sha256']}` | — |",
        f"| uncertain calls | `{meta['ledger_uncertain_calls']}` | 0 |",
        "",
        "### 2.1 Ledger 明细",
        "",
        "| seq | run | kind | metric | status | input | output | cost CNY |",
        "|---:|---|---|---|---|---:|---:|---:|",
    ]
    for row in ledger["rows"]:
        lines.append(
            f"| {row['seq']} | {row['run_id']} | {row['kind']} | "
            f"{row['metric']} | {row['status']} | {row['input_tokens']} | "
            f"{row['output_tokens']} | {row['cost_cny']:.8f} |"
        )
    lines.extend(
        [
            "",
            "## 3. Q23 F 逐次",
            "",
            "| run | status | F | F_strict | scorable | supported | unsupported | "
            "insufficient | patch | target hit |",
            "|---|---|---:|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for run in q23["runs"]:
        counts = run.get("counts") or {}
        patch = run.get("patch") or {}
        lines.append(
            f"| {run['run_id']} | {run.get('f_status')} | {run.get('f_score')} | "
            f"{run.get('f_strict_score')} | {counts.get('scorable_claim_count')} | "
            f"{counts.get('supported_count')} | {counts.get('unsupported_count')} | "
            f"{counts.get('insufficient_evidence_count')} | "
            f"`{patch.get('applied_claims')}` | {run.get('target_hit')} |"
        )
    lines.extend(
        [
            "",
            "## 4. Q23 汇总",
            "",
            "| 项 | 值 |",
            "|---|---:|",
            f"| valid / invalid runs | {q23_summary_data['valid_run_count']} / "
            f"{q23_summary_data['invalid_run_count']} |",
            f"| median / min / max | {q23_summary_data['median']} / "
            f"{q23_summary_data['min']} / {q23_summary_data['max']} |",
            f"| target hit count / rate | {q23_summary_data['target_hit_count']} / "
            f"{q23_summary_data['target_hit_rate']} |",
            f"| median in target | {q23_summary_data['median_in_target']} |",
            f"| insufficient valid runs | {q23_summary_data['insufficient_valid_runs']} |",
            "",
            "## 5. Q23 claim 分解逐次",
            "",
        ]
    )
    for run in q23["runs"]:
        lines.extend(render_q23_run(run))
    lines.extend(
        [
            "## 6. Q23 C/R snapshot",
            "",
            "| metric | status | score | target | target hit |",
            "|---|---|---:|---|---|",
            f"| answer_correctness | {q23_cr.get('c_status') if q23_cr else None} | "
            f"{q23_cr.get('c_score') if q23_cr else None} | `[0.0,0.2]` | "
            f"{q23_cr.get('c_target_hit') if q23_cr else None} |",
            f"| answer_relevancy | {q23_cr.get('r_status') if q23_cr else None} | "
            f"{q23_cr.get('r_score') if q23_cr else None} | `[0.7,1.0]` | "
            f"{q23_cr.get('r_target_hit') if q23_cr else None} |",
            "",
            "C 首句 warning："
            f"`{q23_cr.get('c_warning') if q23_cr else None}`。"
            "仅作 diagnostic snapshot，不宣称 C/R 稳定。",
            "",
            "## 7. Q21",
            "",
        ]
    )
    if q21:
        lines.extend(render_metric_table(q21.get("metrics") or {}))
        lines.extend(
            [
                "",
                f"- forbidden quote：`{q21.get('forbidden_quote')}`",
                "- exemption claims：`"
                f"{json.dumps(q21.get('exemption_claims'), ensure_ascii=False)}`",
                "",
            ]
        )
    else:
        lines.extend(["未运行或未收集。", ""])
    lines.extend(["## 8. Q11", ""])
    if q11:
        lines.extend(render_metric_table(q11.get("metrics") or {}))
        lines.extend(
            [
                "",
                f"- quote checks：`{json.dumps(q11.get('quote_checks'), ensure_ascii=False)}`",
                "",
            ]
        )
    else:
        lines.extend(["未运行或未收集。", ""])
    lines.extend(
        [
            "## 9. 停止与诊断",
            "",
            f"- stop_triggered：`{meta['stop_triggered']}`",
            f"- stop_reason：{meta['stop_reason'] or '—'}",
            f"- stop_codes：`{meta['stop_codes']}`",
            f"- completed runs：`{results['completed_runs']}`",
            f"- missing runs：`{results['missing_runs']}`",
            "",
            "## 10. 交付声明",
            "",
            "- diagnostic only；不是 10 条，也不是 40 条；不计入 10 条样本。",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora/RAG adapter。",
            "- 未激活 v1.2.5；active/runtime_active 保持 false；默认仍 `v1.0.0`。",
            "- 未跑 10/40；未写 PASS；不替代正式验收。",
            "- 未修改 v1.2.5 frozen 资产/target/fixture。",
            "- M1-D-6 仍 `blocked`；M1-C/M1-D 未 accepted。",
            "",
            "## 11. 资产 SHA",
            "",
            "| 项 | 值 |",
            "|---|---|",
            f"| application | `{meta['application_sha256']}` |",
            f"| F / C / R | `{meta['preflight']['prompt_sha256']['faithfulness.txt']}` / "
            f"`{meta['preflight']['prompt_sha256']['answer_correctness.txt']}` / "
            f"`{meta['preflight']['prompt_sha256']['answer_relevancy.txt']}` |",
            f"| MANIFEST / validation | `{meta['manifest_sha256']}` / "
            f"`{meta['validation_sha256']}` |",
            f"| patch schema / example | `{meta['patch_schema_sha256']}` / "
            f"`{meta['patch_example_sha256']}` |",
            f"| quote validator / leakage | `{meta['quote_validator_sha256']}` / "
            f"`{meta['leakage_audit_sha256']}` |",
            f"| fixture / target / labels | `{meta['fixture_sha256']}` / "
            f"`{meta['target_sha256']}` / `{meta['labels_sha256']}` |",
            f"| agent / freeze | `{meta['agent_commit']}` / `{meta['freeze_commit']}` |",
            f"| ledger | `{meta['ledger_sha256']}` |",
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

    ledger = LedgerWriter(
        LEDGER_FILE,
        EXPECTED_LEDGER_INITIAL_SHA,
        require_empty=True,
    )
    recorder = CallRecorder(ledger=ledger)
    q23_runs: list[dict[str, Any]] = []
    q23_cr: dict[str, Any] | None = None
    q21: dict[str, Any] | None = None
    q11: dict[str, Any] | None = None
    effective_prompts: list[dict[str, Any]] = []
    stop_reason: str | None = None
    stop_codes: list[str] = []
    fixture = preflight_result["fixture"]
    q23_case = dataset_case(fixture, "Q23")
    q21_case = dataset_case(fixture, "Q21")
    q11_case = dataset_case(fixture, "Q11")

    try:
        async with LLMClient() as real_llm:
            for index in range(1, Q23_F_RUNS + 1):
                run_id = f"Q23-F{index}"
                outcomes = await run_one(
                    recorder=recorder,
                    real_llm=real_llm,
                    fixture_case=q23_case,
                    case_id="Q23",
                    run_id=run_id,
                    metrics=["faithfulness"],
                    effective_prompts=effective_prompts,
                )
                ledger_errors = validate_ledger_run(ledger, run_id)
                run = q23_run_record(
                    run_id=run_id,
                    outcomes=outcomes,
                    recorder=recorder,
                    ledger_errors=ledger_errors,
                )
                q23_runs.append(run)
                hard_reason, hard_codes = check_hard_stop(
                    recorder=recorder,
                    ledger=ledger,
                    runs=q23_runs,
                    run_id=run_id,
                    fingerprint_errors=run["fingerprint_errors"],
                    credential_failure=run["credential_failure"],
                    ledger_errors=ledger_errors,
                )
                print(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "f_status": run["f_status"],
                            "f_score": run["f_score"],
                            "calls": recorder.judge_calls,
                            "cost_cny": round(recorder.cost, 8),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if hard_reason:
                    stop_reason = hard_reason
                    stop_codes = hard_codes
                    break

            if stop_reason is None:
                outcomes = await run_one(
                    recorder=recorder,
                    real_llm=real_llm,
                    fixture_case=q23_case,
                    case_id="Q23",
                    run_id="Q23-CR",
                    metrics=["answer_correctness", "answer_relevancy"],
                    effective_prompts=effective_prompts,
                )
                ledger_errors = validate_ledger_run(ledger, "Q23-CR")
                q23_cr = q23_cr_record(
                    run_id="Q23-CR",
                    outcomes=outcomes,
                    recorder=recorder,
                )
                hard_reason, hard_codes = check_hard_stop(
                    recorder=recorder,
                    ledger=ledger,
                    runs=q23_runs,
                    run_id="Q23-CR",
                    fingerprint_errors=q23_cr["fingerprint_errors"] + ledger_errors,
                    credential_failure=False,
                    ledger_errors=ledger_errors,
                )
                if hard_reason:
                    stop_reason = hard_reason
                    stop_codes = hard_codes

            if stop_reason is None:
                outcomes = await run_one(
                    recorder=recorder,
                    real_llm=real_llm,
                    fixture_case=q21_case,
                    case_id="Q21",
                    run_id="Q21",
                    metrics=None,
                    effective_prompts=effective_prompts,
                )
                ledger_errors = validate_ledger_run(ledger, "Q21")
                q21 = q21_record(
                    run_id="Q21",
                    outcomes=outcomes,
                    recorder=recorder,
                )
                hard_reason, hard_codes = check_hard_stop(
                    recorder=recorder,
                    ledger=ledger,
                    runs=q23_runs,
                    run_id="Q21",
                    fingerprint_errors=q21["fingerprint_errors"] + ledger_errors,
                    credential_failure=any(
                        outcome.details.get("failure_kind") == "credential"
                        for outcome in outcomes
                    ),
                    ledger_errors=ledger_errors,
                )
                if hard_reason:
                    stop_reason = hard_reason
                    stop_codes = hard_codes

            if stop_reason is None:
                outcomes = await run_one(
                    recorder=recorder,
                    real_llm=real_llm,
                    fixture_case=q11_case,
                    case_id="Q11",
                    run_id="Q11",
                    metrics=None,
                    effective_prompts=effective_prompts,
                )
                ledger_errors = validate_ledger_run(ledger, "Q11")
                q11 = q11_record(
                    run_id="Q11",
                    outcomes=outcomes,
                    recorder=recorder,
                    contexts=[ctx["content"] for ctx in q11_case["contexts"]],
                )
                hard_reason, hard_codes = check_hard_stop(
                    recorder=recorder,
                    ledger=ledger,
                    runs=q23_runs,
                    run_id="Q11",
                    fingerprint_errors=q11["fingerprint_errors"] + ledger_errors,
                    credential_failure=any(
                        outcome.details.get("failure_kind") == "credential"
                        for outcome in outcomes
                    ),
                    ledger_errors=ledger_errors,
                )
                if hard_reason:
                    stop_reason = hard_reason
                    stop_codes = hard_codes
    except Exception as exc:  # noqa: BLE001
        stop_reason = f"runner_exception: {type(exc).__name__}: {exc}"
        stop_codes = ["runner_exception"]

    results = build_results(
        preflight_result=preflight_result,
        recorder=recorder,
        ledger=ledger,
        q23_runs=q23_runs,
        q23_cr=q23_cr,
        q21=q21,
        q11=q11,
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
    OUT_SHA.write_text(
        f"{json_sha}  {OUT_JSON.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    report = write_report(results, json_sha)
    OUT_MD.write_text(report, encoding="utf-8", newline="\n")
    md_sha = sha256_bytes(OUT_MD.read_bytes())
    print(
        json.dumps(
            {
                "status": results["meta"]["status"],
                "stop_triggered": results["meta"]["stop_triggered"],
                "stop_reason": results["meta"]["stop_reason"],
                "q23_f_median": results["meta"]["q23_f_median"],
                "q23_f_min": results["meta"]["q23_f_min"],
                "q23_f_max": results["meta"]["q23_f_max"],
                "ledger_sha256": results["meta"]["ledger_sha256"],
                "ledger_total_attempts": results["meta"]["ledger_total_attempts"],
                "ledger_uncertain_calls": results["meta"]["ledger_uncertain_calls"],
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
    asyncio.run(main())
