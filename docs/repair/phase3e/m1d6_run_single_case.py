"""M1-D-6 v1.2.4 Q23/Q21/Q11 single-case diagnostic run.

Approved single-case diagnostic:
- 3 cases x 1 run x 3 metrics = 9 primary Judge calls
- 3 patch reserve + 2 retry reserve
- max 14 Judge calls / CNY 0.30
- judge_trace(session=None, ...) only; no RagEvaluationRun, no DB write,
  no WeKnora/RAG adapter, no v1.2.4 activation.
- append-only ledger at the LLM boundary: every llm.chat gets started before
  the call and finished after it; primary/patch/retry are all counted; a
  started record without finished is an uncertain call.

Run from the repository root with the approved DASHSCOPE_API_KEY present:
    .\\backend\\venv\\Scripts\\python.exe docs/repair/phase3e/m1d6_run_single_case.py

Preflight only (no Judge call, no real-ledger write):
    .\\backend\\venv\\Scripts\\python.exe ^
        docs/repair/phase3e/m1d6_run_single_case.py --preflight-only
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
    raise SystemExit("DASHSCOPE_API_KEY is required for the approved qwen-max replay")
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

APPLICATION_FILE = (
    BASE / "docs/repair/phase3e/m1d6-single-case-diagnostic-application.json"
)
FIXTURE_FILE = BASE / "docs/repair/phase3e/pilot-10-v1.1.5-gate.json"
TARGET_FILE = BASE / "docs/repair/phase3e/pilot-40-targets-v1.2.0-v1.0.2.json"
LABELS_FILE = BASE / "docs/repair/phase3e/pilot-40-final-labels.json"
MANIFEST_FILE = BASE / "backend/app/prompts/rag_judge/v1.2.4/MANIFEST.json"
VALIDATION_FILE = BASE / "docs/repair/phase3e/m1d6-prompt-v1.2.4-validation.json"
LEAKAGE_AUDIT_FILE = BASE / "docs/repair/phase3e/m1d6-prompt-leakage-audit.json"
PROMPT_DIR = BASE / "backend/app/prompts/rag_judge/v1.2.4"
PATCH_SCHEMA_FILE = BASE / "backend/app/schemas/agents/rag_judge_patch.py"
LEDGER_FILE = BASE / "docs/repair/phase3e/m1d6-single-case-ledger.jsonl"
OUT_JSON = BASE / "docs/repair/phase3e/m1d6-single-case-results.json"
OUT_MD = BASE / "docs/repair/49-m1d6-v1.2.4-single-case-diagnostic-results.md"
OUT_SHA = BASE / "docs/repair/phase3e/m1d6-single-case-results.sha256"

EXPECTED_APPLICATION_SHA = (
    "54193e918daf3111014790923431695c7641fb629d2341bd71ecbe03001b1388"
)
EXPECTED_FIXTURE_SHA = (
    "dc7be14b6026b579c15dea1a13d498b7479e14081aa17419ef2bfa525ae9be70"
)
EXPECTED_TARGET_SHA = "3ee15dfca66fe13f0a45fda84ecf2612483f2de107ad079b196a6bd6344d5846"
EXPECTED_LABELS_SHA = "f139623fef80b55716fce0c773e776d284a5167683eb91559b23e49cabd000eb"
EXPECTED_MANIFEST_SHA = (
    "33cad3a810056bc01ead8a9c943702e439d9af7be62a568df221b1336551bc66"
)
EXPECTED_VALIDATION_SHA = (
    "9ecdb4241be87e6fd3ddd68d9da337f3a321af24f518d25c20fff77f1e5212bc"
)
EXPECTED_LEAKAGE_AUDIT_SHA = (
    "7a5fa6182ae4eebff2f24b48133fe081f05b8096d249b76498cada48661dcce4"
)
EXPECTED_PATCH_SCHEMA_SHA = (
    "da70dc607aaf70879cf40e3420bc5440829b05d9be344a07907947df8c891cb8"
)
EXPECTED_PATCH_EXAMPLE_SHA = (
    "629d74ac3bba3a36372c8a54796de6c5c91fc59b20a235061e0c86ae39129a47"
)
EXPECTED_QUOTE_VALIDATOR_SHA = (
    "153ab4a6f203ca0398133a2cc2ca6fda834f7670afa90651c66cfa44b92c722a"
)
EXPECTED_PROMPT_SHA = {
    "faithfulness.txt": "52f1b3cf3b92d6f9616e73ed7de26a0721d65c27763f48edd41b38f1e06a025d",
    "answer_correctness.txt": "ca489fcf39691e9a71aec004a01938fb6c70b7b17da3c55fb0ada066e1d24968",
    "answer_relevancy.txt": "f3efe431683ed26ba0a7338e6e2b5841d65d42dadde5cac30b8340e2ca95dfdc",
}
EXPECTED_LEDGER_INITIAL_SHA = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
EXPECTED_AGENT_COMMIT = "8dcd53d"
EXPECTED_INITIAL_COMMIT = "88810fd"
EXPECTED_PATCH_PROMPT_FIX_COMMIT = "8dcd53d"
EXPECTED_STATUS_DOC_COMMIT = "f761fa7"
EXPECTED_FREEZE_COMMIT = "c813443"

PROMPT_VERSION = "v1.2.4"
RUBRIC_VERSION = "v1.2.0"
SCHEMA_VERSION = "rag_judge_schema_v3"
METRIC_VERSION = "v3"
CASE_IDS = ("Q23", "Q21", "Q11")
MAX_JUDGE_CALLS = 14
CEILING_CNY = 0.30
PRICE_INPUT = 0.0024 / 1000
PRICE_OUTPUT = 0.0096 / 1000
FIXED_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "m1d6:single-case:user")
ABSENCE_MARKERS = ("未提及", "未说明", "未规定", "未涉及", "没有提及", "没有说明")
EXEMPTION_MARKERS = ("不受", "不适用", "除外", "例外", "仍可", "可以申请")
SPECIFIC_GOODS_MARKERS = ("定制", "生鲜", "虚拟")

STOP_CONDITION_DEFS = (
    ("invalid_contract", "任一指标 invalid(contract_violation)"),
    ("schema_or_patch_failure", "初始 Schema 失败，或 patch 1 次后仍失败"),
    ("q23_patch_semantic_change", "Q23 patch 改了 cl1 或其它非目标 claim"),
    ("q23_absence_contract", "Q23 absence 仍为 factual/supported"),
    ("q23_f_or_c_target", "Q23 F 或 C 目标 miss"),
    ("q21_semantic_or_f_one", "Q21 F=1.0，或仍用运费/换货 quote 支持 7 天豁免"),
    ("q11_quote_or_target", "Q11 quote/契约违约，或三项目标任一 miss"),
    (
        "fingerprint_mismatch",
        "Prompt/MANIFEST/fixture/target/patch schema/example/validator SHA 漂移",
    ),
    ("budget_ceiling", "超过 14 calls 或 CNY 0.30"),
    (
        "ledger_or_missing_result",
        "ledger 缺失/SHA 不匹配/uncertain_call=true，或任一 case 缺完整 F/C/R",
    ),
)


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


def effective_claim_id(claim: dict[str, Any], index: int) -> str:
    return str(claim.get("claim_id") or f"cl{index}")


def claim_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    claims = list(payload.get("claims") or [])
    return {
        effective_claim_id(claim, index): claim for index, claim in enumerate(claims, 1)
    }


class LedgerError(RuntimeError):
    """Ledger integrity failure; the diagnostic must stop."""


class BudgetExceeded(RuntimeError):
    """Raised before a Judge call that would exceed the approved budget."""


@dataclass
class LedgerWriter:
    """Append-only JSONL ledger written at the LLM boundary."""

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
            raise LedgerError(
                "ledger is not empty at run start; previous partial run or rerun is not allowed"
            )
        if data:
            self._replay(data)

    def _replay(self, data: bytes) -> None:
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            self.entries.append(record)
            if record.get("event") == "started":
                seq = int(record["seq"])
                self._seq = max(self._seq, seq)
                self.attempts += 1
                self._open[seq] = record
            elif record.get("event") == "finished":
                seq = int(record["seq"])
                self._open.pop(seq, None)
                usage = record.get("usage") or {}
                self.input_tokens += int(usage.get("input") or 0)
                self.output_tokens += int(usage.get("output") or 0)

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
            raise LedgerError(f"finished record without started seq={seq}")
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

    def by_case_metric(self) -> dict[str, dict[str, Any]]:
        finished_by_seq = {
            int(record["seq"]): record for record in self.finished_records()
        }
        summary: dict[str, dict[str, Any]] = {}
        for started in self.started_records():
            seq = int(started["seq"])
            finished = finished_by_seq.get(seq) or {}
            case_id = str(started.get("case_id") or "?")
            metric = str(started.get("metric") or "?")
            key = f"{case_id}/{metric}"
            bucket = summary.setdefault(
                key,
                {
                    "case_id": case_id,
                    "metric": metric,
                    "calls": 0,
                    "primary": 0,
                    "patch": 0,
                    "repair": 0,
                    "retry": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_cny": 0.0,
                },
            )
            bucket["calls"] += 1
            kind = str(started.get("kind") or "primary")
            bucket[kind] = bucket.get(kind, 0) + 1
            usage = finished.get("usage") or {}
            bucket["input_tokens"] += int(usage.get("input") or 0)
            bucket["output_tokens"] += int(usage.get("output") or 0)
            bucket["cost_cny"] = round(
                bucket["cost_cny"] + float(finished.get("cost_cny") or 0.0), 8
            )
        return summary

    def summary(self) -> dict[str, Any]:
        started = self.started_records()
        finished = self.finished_records()
        started_by_kind = Counter(
            str(record.get("kind") or "primary") for record in started
        )
        finished_by_kind = Counter(
            str(
                next(
                    (
                        item.get("kind")
                        for item in started
                        if int(item["seq"]) == int(record["seq"])
                    ),
                    "unknown",
                )
            )
            for record in finished
        )
        return {
            "ledger_file": str(self.path.relative_to(BASE)),
            "ledger_sha256": self.sha256,
            "initial_sha256": self.initial_sha256,
            "total_attempts": self.attempts,
            "finished_calls": len(finished),
            "uncertain_calls": self.uncertain_calls,
            "started_by_kind": dict(started_by_kind),
            "finished_by_kind": dict(finished_by_kind),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_cny": round(self.cost, 8),
            "ceiling_cny": CEILING_CNY,
            "max_judge_calls": MAX_JUDGE_CALLS,
            "budget_error": self.budget_error,
            "by_case_metric": self.by_case_metric(),
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
    def input_tokens(self) -> int:
        return self.ledger.input_tokens

    @property
    def output_tokens(self) -> int:
        return self.ledger.output_tokens

    @property
    def cost(self) -> float:
        return self.ledger.cost

    @property
    def primary_calls(self) -> int:
        return sum(1 for call in self.calls if call["kind"] == "primary")

    @property
    def patch_calls(self) -> int:
        return sum(1 for call in self.calls if call["kind"] == "patch")

    @property
    def repair_calls(self) -> int:
        return sum(1 for call in self.calls if call["kind"] == "repair")

    @property
    def retry_calls(self) -> int:
        return sum(1 for call in self.calls if call["kind"] == "retry")

    def for_case(self, case_id: str, metric: str | None = None) -> list[dict[str, Any]]:
        return [
            call
            for call in self.calls
            if call["case_id"] == case_id
            and (metric is None or call["metric"] == metric)
        ]


class InstrumentedLLM:
    """Delegates to LLMClient while recording every Judge/patch/repair call."""

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
        except Exception as exc:  # noqa: BLE001 - record and preserve the failure
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


def synthetic_trace(case: dict[str, Any]) -> RagTrace:
    case_id = case["id"]
    return RagTrace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"m1d6:single-case:{case_id}"),
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


def direct_exemption_quote(quote: str) -> bool:
    text = normalized(quote)
    if any(marker in text for marker in SPECIFIC_GOODS_MARKERS):
        return False
    return (
        "质量问题" in text
        and any(marker in text for marker in EXEMPTION_MARKERS)
        and ("7天" in text or "七天" in text or "无理由" in text)
    )


def q23_patch_review(patch_trace: dict[str, Any]) -> dict[str, Any]:
    initial_text = patch_trace.get("initial_output")
    patch_text = patch_trace.get("patch_output")
    merged_text = patch_trace.get("merged_output")
    review: dict[str, Any] = {
        "patch_triggered": bool(patch_text),
        "initial_output_present": bool(initial_text),
        "patch_output_present": bool(patch_text),
        "merged_output_present": bool(merged_text),
        "patch_example_quote_copied": False,
        "non_target_claims_unchanged": None,
        "changed_claims": [],
        "changed_outside_applied": [],
        "failures": [],
    }
    if patch_text and PATCH_EXAMPLE_CONTEXT in patch_text:
        review["patch_example_quote_copied"] = True
        review["failures"].append("patch copied the example quote")
    if not initial_text or not merged_text:
        review["failures"].append("initial or merged output missing")
        return review
    try:
        initial = json.loads(extract_json_text(initial_text))
        merged = json.loads(extract_json_text(merged_text))
    except (TypeError, ValueError) as exc:
        review["failures"].append(f"cannot parse initial/merged output: {exc}")
        return review
    initial_claims = claim_map(initial)
    merged_claims = claim_map(merged)
    applied = set(patch_trace.get("patch_applied_claims") or [])
    changed: list[str] = []
    outside: list[str] = []
    for claim_id in sorted(set(initial_claims) | set(merged_claims)):
        before = initial_claims.get(claim_id)
        after = merged_claims.get(claim_id)
        if before is None or after is None:
            changed.append(claim_id)
            if claim_id not in applied:
                outside.append(claim_id)
            continue
        before_semantics = {
            key: before.get(key)
            for key in (
                "claim",
                "claim_type",
                "claim_subtype",
                "support_status",
                "is_contradictory",
                "contradiction_with",
            )
        }
        after_semantics = {
            key: after.get(key)
            for key in (
                "claim",
                "claim_type",
                "claim_subtype",
                "support_status",
                "is_contradictory",
                "contradiction_with",
            )
        }
        before_refs = before.get("evidence_refs") or []
        after_refs = after.get("evidence_refs") or []
        if before_semantics != after_semantics:
            changed.append(claim_id)
            if claim_id not in applied:
                outside.append(claim_id)
        elif before_refs != after_refs:
            changed.append(claim_id)
            if claim_id not in applied:
                outside.append(claim_id)
    review["changed_claims"] = changed
    review["changed_outside_applied"] = outside
    review["non_target_claims_unchanged"] = not outside
    if outside:
        review["failures"].append(f"patch changed non-applied claims: {outside}")
    return review


def q23_checks(
    f: Any,
    strict: Any,
    c: Any,
    r: Any,
    *,
    patch_trace: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    notes: list[str] = []
    stop_codes: list[str] = []
    if f is None or f.status != "evaluated":
        failures.append(f"Q23 F status={getattr(f, 'status', None)}")
        stop_codes.append("invalid_contract")
    if c is None or c.status != "evaluated":
        failures.append(f"Q23 C status={getattr(c, 'status', None)}")
        stop_codes.append("invalid_contract")
    if r is None or r.status != "evaluated":
        failures.append(f"Q23 R status={getattr(r, 'status', None)}")
        stop_codes.append("invalid_contract")
    details = getattr(f, "details", {}) or {}
    claims = list(details.get("claims") or [])
    contract = details.get("agent_contract") or {}
    if not contract:
        failures.append("Q23 missing agent_contract")
        stop_codes.append("invalid_contract")
    validation_errors = details.get("validation_errors") or []
    final_errors = contract.get("final_errors") or []
    if validation_errors:
        failures.append(f"Q23 quote errors remain: {validation_errors}")
        stop_codes.append("invalid_contract")
    if final_errors:
        failures.append(f"Q23 agent final_errors: {final_errors}")
        stop_codes.append("schema_or_patch_failure")

    absence_claims = [
        claim for claim in claims if claim.get("claim_subtype") == "absence"
    ]
    absence_fields: list[dict[str, Any]] = []
    if not absence_claims:
        failures.append("Q23 no absence claim found")
        stop_codes.append("q23_absence_contract")
    for claim in absence_claims:
        fields = {
            "claim_id": claim.get("claim_id"),
            "claim": claim.get("claim"),
            "claim_type": claim.get("claim_type"),
            "claim_subtype": claim.get("claim_subtype"),
            "support_status": claim.get("support_status"),
            "evidence_refs": claim.get("evidence_refs") or [],
            "is_contradictory": claim.get("is_contradictory"),
            "contradiction_with": claim.get("contradiction_with") or [],
        }
        absence_fields.append(fields)
        if claim.get("claim_type") != "non_factual":
            failures.append(
                f"Q23 absence {claim.get('claim_id')} type={claim.get('claim_type')}"
            )
            stop_codes.append("q23_absence_contract")
        if claim.get("support_status") is not None:
            failures.append(
                f"Q23 absence {claim.get('claim_id')} support_status="
                f"{claim.get('support_status')!r}"
            )
            stop_codes.append("q23_absence_contract")
        if claim.get("evidence_refs"):
            failures.append(f"Q23 absence {claim.get('claim_id')} has evidence")
            stop_codes.append("q23_absence_contract")
        if claim.get("is_contradictory"):
            failures.append(f"Q23 absence {claim.get('claim_id')} is_contradictory")
            stop_codes.append("q23_absence_contract")
        if claim.get("contradiction_with"):
            failures.append(f"Q23 absence {claim.get('claim_id')} contradiction_with")
            stop_codes.append("q23_absence_contract")

    warnings = list(contract.get("mixed_sentence_warnings") or [])
    warning_claims = {
        str(item.get("claim_id")): str(item.get("claim") or "")
        for item in warnings
        if isinstance(item, dict)
    }
    for claim in claims:
        if claim.get("claim_type") != "factual_claim":
            continue
        if claim.get("claim_subtype") == "absence":
            failures.append(
                f"Q23 factual claim {claim.get('claim_id')} uses absence subtype"
            )
            stop_codes.append("q23_absence_contract")
        text = str(claim.get("claim") or "")
        if any(marker in text for marker in ABSENCE_MARKERS):
            claim_id = str(claim.get("claim_id") or "")
            if claim_id in warning_claims or text in warning_claims.values():
                notes.append(f"Q23 mixed sentence warning recorded: {claim_id}")
            else:
                failures.append(
                    f"Q23 factual claim {claim_id} mixes absence without warning"
                )
                stop_codes.append("q23_absence_contract")

    patch_applied = list(contract.get("patch_applied_claims") or [])
    patch_triggered = bool(contract.get("repair_triggered"))
    patch_semantic_review_required = bool(
        contract.get("patch_semantic_review_required")
    )
    patch_review = q23_patch_review(patch_trace)
    if patch_review["failures"]:
        failures.extend(
            f"Q23 patch review: {item}" for item in patch_review["failures"]
        )
        stop_codes.append("q23_patch_semantic_change")
    if patch_triggered:
        if not patch_applied:
            failures.append("Q23 patch triggered but patch_applied_claims is empty")
            stop_codes.append("q23_patch_semantic_change")
        extra = sorted(set(patch_applied) - {"cl2", "cl3"})
        if extra:
            failures.append(f"Q23 patch applied non-target claims: {extra}")
            stop_codes.append("q23_patch_semantic_change")
        if not patch_semantic_review_required:
            failures.append("Q23 patch_semantic_review_required is false")
            stop_codes.append("q23_patch_semantic_change")
    cl1 = next((claim for claim in claims if claim.get("claim_id") == "cl1"), None)
    if cl1 is None:
        failures.append("Q23 cl1 missing")
        stop_codes.append("q23_patch_semantic_change")
    elif cl1.get("support_status") != "supported":
        failures.append(f"Q23 cl1 support_status={cl1.get('support_status')!r}")
        stop_codes.append("q23_patch_semantic_change")

    if strict is not None and strict.status == "evaluated":
        pass
    elif (
        strict is not None
        and strict.status == "skipped"
        and strict.skipped_reason == "no_decidable_claims"
        and f is not None
        and f.score == 0.0
        and details.get("all_insufficient") is True
        and details.get("supported_count") == 0
        and details.get("unsupported_count") == 0
    ):
        notes.append("Q23 F_strict skipped(no_decidable_claims) allowed by exception")
    else:
        failures.append(f"Q23 F_strict status={getattr(strict, 'status', None)}")
        stop_codes.append("invalid_contract")

    f_pass = in_target(getattr(f, "score", None), [0.4, 0.5])
    c_pass = in_target(getattr(c, "score", None), [0.0, 0.2])
    r_pass = in_target(getattr(r, "score", None), [0.7, 1.0])
    if not f_pass:
        failures.append(f"Q23 F target [0.4, 0.5] miss: {getattr(f, 'score', None)}")
        stop_codes.append("q23_f_or_c_target")
    if not c_pass:
        failures.append(f"Q23 C target [0.0, 0.2] miss: {getattr(c, 'score', None)}")
        stop_codes.append("q23_f_or_c_target")
    if not r_pass:
        failures.append(f"Q23 R target [0.7, 1.0] miss: {getattr(r, 'score', None)}")
        stop_codes.append("q23_target_r")
    return {
        "passed": not failures,
        "failures": failures,
        "notes": notes,
        "stop_codes": sorted(set(stop_codes)),
        "target_pass": f_pass and c_pass and r_pass,
        "f_target_pass": f_pass,
        "c_target_pass": c_pass,
        "r_target_pass": r_pass,
        "absence_count": len(absence_claims),
        "absence_fields": absence_fields,
        "mixed_sentence_warnings": warnings,
        "patch_triggered": patch_triggered,
        "patch_applied_claims": patch_applied,
        "patch_semantic_review_required": patch_semantic_review_required,
        "patch_review": patch_review,
        "claims": claims,
        "agent_contract": contract,
    }


def q21_checks(f: Any, contexts: list[str]) -> dict[str, Any]:
    failures: list[str] = []
    notes: list[str] = []
    stop_codes: list[str] = []
    if f is None or f.status != "evaluated":
        failures.append(f"Q21 F status={getattr(f, 'status', None)}")
        stop_codes.append("invalid_contract")
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
        stop_codes.append("q21_semantic_or_f_one")
    exemption_details: list[dict[str, Any]] = []
    for claim in exemption_claims:
        claim_id = claim.get("claim_id")
        status = claim.get("support_status")
        quotes = [
            str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])
        ]
        detail = {
            "claim_id": claim_id,
            "claim": claim.get("claim"),
            "support_status": status,
            "quotes": quotes,
            "direct_exemption_quote": any(
                direct_exemption_quote(quote) for quote in quotes
            ),
            "forbidden_quote": any(
                ("运费" in quote or "换货" in quote) and not direct_exemption_quote(quote)
                for quote in quotes
            ),
        }
        exemption_details.append(detail)
        if status == "insufficient_evidence":
            notes.append(f"Q21 {claim_id} insufficient_evidence")
            if quotes:
                failures.append(
                    f"Q21 {claim_id} insufficient_evidence must not have quotes"
                )
                stop_codes.append("q21_semantic_or_f_one")
        elif status == "supported" and any(
            direct_exemption_quote(quote) for quote in quotes
        ):
            notes.append(f"Q21 {claim_id} supported by direct exemption quote")
        else:
            failures.append(f"Q21 {claim_id} status={status!r} quotes={quotes!r}")
            stop_codes.append("q21_semantic_or_f_one")
        if detail["forbidden_quote"]:
            failures.append(f"Q21 {claim_id} uses freight/exchange quote")
            stop_codes.append("q21_semantic_or_f_one")
    for claim in claims:
        text = normalized(claim.get("claim") or "")
        if "普通商品" not in text or claim.get("support_status") != "supported":
            continue
        quotes = [
            str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])
        ]
        if not any(
            "普通商品" in normalized(quote)
            and ("7天" in normalized(quote) or "无理由" in normalized(quote))
            for quote in quotes
        ):
            failures.append(
                f"Q21 exclusion inference {claim.get('claim_id')} marked supported"
            )
            stop_codes.append("q21_semantic_or_f_one")
    score = getattr(f, "score", None)
    details = getattr(f, "details", {}) or {}
    contract = details.get("agent_contract") or {}
    if not contract:
        failures.append("Q21 missing agent_contract")
        stop_codes.append("invalid_contract")
    if score == 1.0:
        failures.append("Q21 F=1.0 is a stop condition")
        stop_codes.append("q21_semantic_or_f_one")
    target_pass = in_target(score, [0.6, 0.7])
    semantic_pass = not failures
    return {
        "passed": semantic_pass and target_pass,
        "semantic_pass": semantic_pass,
        "semantic_pass_target_miss": semantic_pass and not target_pass,
        "failures": failures,
        "notes": notes,
        "stop_codes": sorted(set(stop_codes)),
        "target_pass": target_pass,
        "f_score": score,
        "f_is_one": score == 1.0,
        "exemption_claims": exemption_details,
        "claims": claims,
        "contexts_checked": len(contexts),
        "agent_contract": contract,
    }


def q11_checks(f: Any, c: Any, r: Any, contexts: list[str]) -> dict[str, Any]:
    failures: list[str] = []
    target_failures: list[str] = []
    stop_codes: list[str] = []
    for name, outcome, target in (
        ("F", f, [0.6, 0.9]),
        ("C", c, [0.8, 1.0]),
        ("R", r, [0.9, 1.0]),
    ):
        if outcome is None or not in_target(getattr(outcome, "score", None), target):
            target_failures.append(
                f"Q11 {name} target {target} miss: {getattr(outcome, 'score', None)}"
            )
            stop_codes.append("q11_quote_or_target")
    failures.extend(target_failures)
    for name, outcome in (("F", f), ("C", c), ("R", r)):
        if outcome is None or outcome.status != "evaluated":
            failures.append(f"Q11 {name} status={getattr(outcome, 'status', None)}")
            stop_codes.append("invalid_contract")
    details = getattr(f, "details", {}) or {}
    contract = details.get("agent_contract") or {}
    if not contract:
        failures.append("Q11 missing agent_contract")
        stop_codes.append("invalid_contract")
    if details.get("validation_errors"):
        failures.append(f"Q11 F validation_errors: {details.get('validation_errors')}")
        stop_codes.append("invalid_contract")
    if contract.get("final_errors"):
        failures.append(f"Q11 F final_errors: {contract.get('final_errors')}")
        stop_codes.append("schema_or_patch_failure")
    claims = list(details.get("claims") or [])
    quote_checks: list[dict[str, Any]] = []
    quote_ok = True
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
                    "has_ellipsis": "…" in quote or "..." in quote,
                }
            )
            if not found:
                quote_ok = False
                failures.append(f"Q11 quote not contiguous: {quote!r}")
                stop_codes.append("q11_quote_or_target")
            if "…" in quote or "..." in quote:
                quote_ok = False
                failures.append(f"Q11 quote contains ellipsis: {quote!r}")
                stop_codes.append("q11_quote_or_target")
    return {
        "passed": not failures,
        "failures": failures,
        "notes": [],
        "stop_codes": sorted(set(stop_codes)),
        "target_pass": not target_failures,
        "quote_pass": quote_ok,
        "quote_checks": quote_checks,
        "claims": claims,
        "agent_contract": contract,
    }


def call_summary(recorder: CallRecorder) -> dict[str, Any]:
    return {
        "judge_calls": recorder.judge_calls,
        "primary_calls": recorder.primary_calls,
        "patch_calls": recorder.patch_calls,
        "repair_calls": recorder.repair_calls,
        "retry_calls": recorder.retry_calls,
        "input_tokens": recorder.input_tokens,
        "output_tokens": recorder.output_tokens,
        "cost_cny": round(recorder.cost, 8),
        "max_judge_calls": MAX_JUDGE_CALLS,
        "ceiling_cny": CEILING_CNY,
    }


def case_call_summary(recorder: CallRecorder, case_id: str) -> dict[str, Any]:
    calls = recorder.for_case(case_id)
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
        "diff",
        "--quiet",
        EXPECTED_AGENT_COMMIT,
        "--",
        "backend/app/agents/rag_judge_agent.py",
    )
    frozen_assets_diff = run(
        "diff",
        "--quiet",
        EXPECTED_FREEZE_COMMIT,
        "--",
        "backend/app/prompts/rag_judge/v1.2.4",
        "backend/app/agents/rag_judge_agent.py",
        "backend/app/services/rag_judge_service.py",
        "backend/app/schemas/agents/rag_judge.py",
        "backend/app/schemas/agents/rag_judge_patch.py",
        "backend/app/schemas/agents/rag_judge_evidence.py",
    )
    commits = {
        "agent": run("cat-file", "-e", f"{EXPECTED_AGENT_COMMIT}^{{commit}}"),
        "initial": run("cat-file", "-e", f"{EXPECTED_INITIAL_COMMIT}^{{commit}}"),
        "patch_prompt_fix": run(
            "cat-file", "-e", f"{EXPECTED_PATCH_PROMPT_FIX_COMMIT}^{{commit}}"
        ),
        "status_doc": run("cat-file", "-e", f"{EXPECTED_STATUS_DOC_COMMIT}^{{commit}}"),
        "freeze": run("cat-file", "-e", f"{EXPECTED_FREEZE_COMMIT}^{{commit}}"),
    }
    errors: list[str] = []
    if head.returncode != 0:
        errors.append(f"git head={head.returncode}")
    if agent_diff.returncode != 0:
        errors.append(
            f"agent_diff={agent_diff.returncode}: {agent_diff.stderr.strip()}"
        )
    if frozen_assets_diff.returncode != 0:
        errors.append(
            "frozen_assets_diff="
            f"{frozen_assets_diff.returncode}: {frozen_assets_diff.stderr.strip()}"
        )
    for name, result in commits.items():
        if result.returncode != 0:
            errors.append(f"{name}_commit={result.returncode}")
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "agent_commit": EXPECTED_AGENT_COMMIT,
        "initial_implementation_commit": EXPECTED_INITIAL_COMMIT,
        "patch_prompt_fix_commit": EXPECTED_PATCH_PROMPT_FIX_COMMIT,
        "status_doc_commit": EXPECTED_STATUS_DOC_COMMIT,
        "freeze_commit": EXPECTED_FREEZE_COMMIT,
        "agent_file_unchanged_since_agent_commit": agent_diff.returncode == 0,
        "frozen_assets_unchanged_since_freeze_commit": frozen_assets_diff.returncode
        == 0,
        "commits_present": {
            name: result.returncode == 0 for name, result in commits.items()
        },
        "errors": errors,
    }


class _FakeLLM:
    """Deterministic primary + patch response for the preflight ledger self-test."""

    def __init__(self, primary_json: str, patch_json: str) -> None:
        self.primary_json = primary_json
        self.patch_json = patch_json

    async def chat(
        self,
        messages: Any,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: Any = None,
    ) -> Any:
        del model, temperature, max_tokens, response_format
        system_text = "\n".join(
            str(message.get("content") or "")
            for message in messages
            if message.get("role") == "system"
        )
        content = (
            self.patch_json
            if "evidence patch 修复器" in system_text
            else self.primary_json
        )
        return SimpleNamespace(
            content=content,
            model="fake-qwen-max",
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            latency_ms=1.0,
        )


async def ledger_self_test() -> dict[str, Any]:
    """Assert one primary + one patch produces two started ledger records."""
    context_text = "订单签收后 7 天内可申请无理由退款。" "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。"
    primary = {
        "claims": [
            {
                "claim_id": "cl1",
                "claim": "订单签收后 7 天内可申请无理由退款",
                "claim_type": "factual_claim",
                "claim_subtype": "policy",
                "support_status": "supported",
                "evidence_refs": [{"context_id": "C1", "quote": "订单签收后 7 天内可申请无理由退款。"}],
                "reason": "",
            },
            {
                "claim_id": "cl2",
                "claim": "定制类商品不支持无理由退款",
                "claim_type": "factual_claim",
                "claim_subtype": "policy",
                "support_status": "supported",
                "evidence_refs": [{"context_id": "C1", "quote": "示例里不存在的句子"}],
                "reason": "",
            },
        ],
        "reason": "",
    }
    patch = {
        "fixes": [
            {
                "claim_id": "cl2",
                "evidence_refs": [
                    {
                        "context_id": "C1",
                        "quote": "定制类商品、生鲜食品、已激活的虚拟商品不支持无理由退款。",
                    }
                ],
            }
        ]
    }
    with tempfile.TemporaryDirectory(prefix="m1d6-ledger-selftest-") as tmp:
        ledger_path = Path(tmp) / "ledger.jsonl"
        ledger_path.write_bytes(b"")
        ledger = LedgerWriter(
            ledger_path,
            EXPECTED_LEDGER_INITIAL_SHA,
            require_empty=True,
        )
        recorder = CallRecorder(ledger=ledger)
        context = {"case_id": "SELFTEST"}
        instrumented = InstrumentedLLM(
            _FakeLLM(
                json.dumps(primary, ensure_ascii=False),
                json.dumps(patch, ensure_ascii=False),
            ),
            recorder,
            context,
            metric="faithfulness",
            metric_sha=EXPECTED_PROMPT_SHA["faithfulness.txt"],
        )
        agent = RagJudgeAgent(
            "faithfulness",
            llm=instrumented,
            prompt_version=PROMPT_VERSION,
        )
        result = await agent.judge(
            {
                "query": "订单签收后第 10 天还能无理由退款吗？",
                "answer": "不可以。",
                "contexts": [context_text],
            },
            session=None,
            scope="m1d6:ledger-self-test",
            user_id=None,
            task_id=None,
        )
        started = ledger.started_records()
        finished = ledger.finished_records()
        started_kinds = [record.get("kind") for record in started]
        errors: list[str] = []
        if not result.success or result.data is None:
            errors.append(f"self-test judge failed: {result.error_type}")
        if started_kinds != ["primary", "patch"]:
            errors.append(f"started_kinds={started_kinds}")
        if len(started) != 2:
            errors.append(f"started_count={len(started)}")
        if len(finished) != 2:
            errors.append(f"finished_count={len(finished)}")
        if len(ledger.entries) != 4:
            errors.append(f"ledger_line_count={len(ledger.entries)}")
        if ledger.uncertain_calls != 0:
            errors.append(f"uncertain_calls={ledger.uncertain_calls}")
        if ledger.attempts != 2:
            errors.append(f"attempts={ledger.attempts}")
        if result.data is not None:
            quote = result.data["claims"][1]["evidence_refs"][0]["quote"]
            if quote.startswith("示例里不存在"):
                errors.append("patch self-test did not replace invalid quote")
        return {
            "ok": not errors,
            "errors": errors,
            "started_kinds": started_kinds,
            "started_records": len(started),
            "finished_records": len(finished),
            "ledger_lines": len(ledger.entries),
            "attempts": ledger.attempts,
            "uncertain_calls": ledger.uncertain_calls,
        }


def application_checks(application: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    meta = application.get("meta") or {}
    run_config = application.get("run_config") or {}
    budget = application.get("budget") or {}
    cases = application.get("cases") or []
    if meta.get("status") != "approved":
        errors.append(f"application status={meta.get('status')!r}")
    if meta.get("scope") != "single_case_diagnostic":
        errors.append(f"application scope={meta.get('scope')!r}")
    if meta.get("case_count") != 3 or meta.get("runs_per_case") != 1:
        errors.append("application case_count/runs_per_case mismatch")
    if meta.get("not_approved_for_10_or_40") is not True:
        errors.append("application is not marked single-case-only")
    if meta.get("judge_run") is not False:
        errors.append("application judge_run is not false")
    if meta.get("runtime_activated") is not False:
        errors.append("application runtime_activated is not false")
    if meta.get("diagnostic_only") is not True:
        errors.append("application diagnostic_only is not true")
    if meta.get("counts_toward_10") is not False:
        errors.append("application counts_toward_10 is not false")
    expected_meta = {
        "manifest_sha256": EXPECTED_MANIFEST_SHA,
        "validation_sha256": EXPECTED_VALIDATION_SHA,
        "leakage_audit_sha256": EXPECTED_LEAKAGE_AUDIT_SHA,
        "patch_schema_sha256": EXPECTED_PATCH_SCHEMA_SHA,
        "patch_example_sha256": EXPECTED_PATCH_EXAMPLE_SHA,
        "quote_validator_sha256": EXPECTED_QUOTE_VALIDATOR_SHA,
        "fixture_sha256": EXPECTED_FIXTURE_SHA,
        "target_sha256": EXPECTED_TARGET_SHA,
        "labels_sha256": EXPECTED_LABELS_SHA,
        "ledger_initial_sha256": EXPECTED_LEDGER_INITIAL_SHA,
        "freeze_commit": EXPECTED_FREEZE_COMMIT,
        "agent_commit": EXPECTED_AGENT_COMMIT,
        "initial_implementation_commit": EXPECTED_INITIAL_COMMIT,
        "status_doc_commit": EXPECTED_STATUS_DOC_COMMIT,
        "prompt_version": PROMPT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "schema_version": SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
    }
    for key, expected in expected_meta.items():
        if meta.get(key) != expected:
            errors.append(f"application meta.{key}={meta.get(key)!r} != {expected!r}")
    if meta.get("prompt_sha256") != EXPECTED_PROMPT_SHA:
        errors.append("application prompt_sha256 mismatch")
    if run_config.get("judge_prompt_version") != PROMPT_VERSION:
        errors.append("application judge_prompt_version mismatch")
    if run_config.get("default_prompt_version") != "v1.0.0":
        errors.append("application default_prompt_version is not v1.0.0")
    if run_config.get("session") is not None:
        errors.append("application session is not null")
    service_path = run_config.get("service_path") or {}
    if service_path.get("creates_run") is not False:
        errors.append("application creates_run is not false")
    if service_path.get("writes_db") is not False:
        errors.append("application writes_db is not false")
    if run_config.get("no_rag_call") is not True:
        errors.append("application no_rag_call is not true")
    if run_config.get("no_platform_run") is not True:
        errors.append("application no_platform_run is not true")
    if run_config.get("no_db_write") is not True:
        errors.append("application no_db_write is not true")
    if run_config.get("no_weknora_call") is not True:
        errors.append("application no_weknora_call is not true")
    if budget.get("max_judge_calls") != MAX_JUDGE_CALLS:
        errors.append(f"application max_judge_calls={budget.get('max_judge_calls')!r}")
    if budget.get("ceiling_cny") != CEILING_CNY:
        errors.append(f"application ceiling_cny={budget.get('ceiling_cny')!r}")
    if budget.get("primary_judge_calls") != 9:
        errors.append(
            f"application primary_judge_calls={budget.get('primary_judge_calls')!r}"
        )
    case_ids = [case.get("case_id") for case in cases]
    if case_ids != list(CASE_IDS):
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
    if manifest.get("default_prompt_version") != "v1.0.0":
        errors.append("manifest default_prompt_version is not v1.0.0")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest schema_version={manifest.get('schema_version')!r}")
    if manifest.get("rubric_version") != RUBRIC_VERSION:
        errors.append(f"manifest rubric_version={manifest.get('rubric_version')!r}")
    if manifest.get("patch_schema_sha256") != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append("manifest patch_schema_sha256 mismatch")
    if manifest.get("patch_example_sha256") != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append("manifest patch_example_sha256 mismatch")
    if manifest.get("quote_validator_sha256") != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append("manifest quote_validator_sha256 mismatch")
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
    return errors


async def preflight() -> dict[str, Any]:
    application = load_json(APPLICATION_FILE)
    target = load_json(TARGET_FILE)
    labels = load_json(LABELS_FILE)
    manifest = load_json(MANIFEST_FILE)
    validation = load_json(VALIDATION_FILE)
    leakage_audit = load_json(LEAKAGE_AUDIT_FILE)
    fixture = load_json(FIXTURE_FILE)

    application_sha = sha256_bytes(APPLICATION_FILE.read_bytes())
    fixture_sha = sha256_bytes(FIXTURE_FILE.read_bytes())
    target_sha = sha256_bytes(TARGET_FILE.read_bytes())
    labels_sha = sha256_bytes(LABELS_FILE.read_bytes())
    manifest_sha = sha256_bytes(MANIFEST_FILE.read_bytes())
    validation_sha = sha256_bytes(VALIDATION_FILE.read_bytes())
    leakage_audit_sha = sha256_bytes(LEAKAGE_AUDIT_FILE.read_bytes())
    patch_schema_sha = sha256_bytes(PATCH_SCHEMA_FILE.read_bytes())
    prompt_sha = {
        name: sha256_bytes((PROMPT_DIR / name).read_bytes())
        for name in EXPECTED_PROMPT_SHA
    }
    agent = RagJudgeAgent("faithfulness", llm=object(), prompt_version=PROMPT_VERSION)
    patch_example_text = agent._patch_example() or ""
    patch_example_sha = sha256_text(patch_example_text)
    validator_sha = quote_validator_sha256()
    ledger_initial_bytes = LEDGER_FILE.read_bytes() if LEDGER_FILE.exists() else b""
    ledger_initial_sha = sha256_bytes(ledger_initial_bytes)
    ledger_self_test_result = await ledger_self_test()
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
    if leakage_audit_sha != EXPECTED_LEAKAGE_AUDIT_SHA:
        errors.append(f"leakage_audit_sha={leakage_audit_sha}")
    if patch_schema_sha != EXPECTED_PATCH_SCHEMA_SHA:
        errors.append(f"patch_schema_sha={patch_schema_sha}")
    if patch_example_sha != EXPECTED_PATCH_EXAMPLE_SHA:
        errors.append(f"patch_example_sha={patch_example_sha}")
    if validator_sha != EXPECTED_QUOTE_VALIDATOR_SHA:
        errors.append(f"quote_validator_sha={validator_sha}")
    if prompt_sha != EXPECTED_PROMPT_SHA:
        errors.append(f"prompt_sha={prompt_sha}")
    if ledger_initial_sha != EXPECTED_LEDGER_INITIAL_SHA:
        errors.append(f"ledger_initial_sha={ledger_initial_sha}")
    if ledger_initial_bytes:
        errors.append(f"ledger is not empty: bytes={len(ledger_initial_bytes)}")
    if not ledger_self_test_result["ok"]:
        errors.append(f"ledger_self_test={ledger_self_test_result['errors']}")
    if leakage_audit.get("status") != "pass" or leakage_audit.get("finding_count") != 0:
        errors.append(
            "leakage audit is not pass/0: "
            f"status={leakage_audit.get('status')!r}, "
            f"findings={leakage_audit.get('finding_count')!r}"
        )
    errors.extend(application_checks(application))
    errors.extend(manifest_checks(manifest, validation))
    errors.extend(git["errors"])

    fixture_cases = {case["id"]: case for case in fixture.get("cases") or []}
    for case_id in CASE_IDS:
        if case_id not in fixture_cases:
            errors.append(f"fixture missing {case_id}")
    if settings.DEFAULT_LLM_MODEL != "qwen-max":
        errors.append(f"model={settings.DEFAULT_LLM_MODEL!r}")
    if settings.DEFAULT_TEMPERATURE != 0.0:
        errors.append(f"temperature={settings.DEFAULT_TEMPERATURE!r}")
    if settings.RAG_JUDGE_MAX_TOKENS != 8192:
        errors.append(f"max_tokens={settings.RAG_JUDGE_MAX_TOKENS!r}")
    if settings.RAG_JUDGE_PROMPT_VERSION != "v1.0.0":
        errors.append(f"default_prompt_version={settings.RAG_JUDGE_PROMPT_VERSION!r}")

    return {
        "application_sha256": application_sha,
        "fixture_sha256": fixture_sha,
        "target_sha256": target_sha,
        "labels_sha256": labels_sha,
        "manifest_sha256": manifest_sha,
        "validation_sha256": validation_sha,
        "leakage_audit_sha256": leakage_audit_sha,
        "leakage_findings": leakage_audit.get("finding_count"),
        "leakage_source_count": leakage_audit.get("source_count"),
        "patch_schema_sha256": patch_schema_sha,
        "patch_example_sha256": patch_example_sha,
        "quote_validator_sha256": validator_sha,
        "prompt_sha256": prompt_sha,
        "ledger_file": str(LEDGER_FILE.relative_to(BASE)),
        "ledger_initial_sha256": ledger_initial_sha,
        "ledger_initial_bytes": len(ledger_initial_bytes),
        "ledger_self_test": ledger_self_test_result,
        "agent_commit": git["agent_commit"],
        "initial_implementation_commit": git["initial_implementation_commit"],
        "patch_prompt_fix_commit": git["patch_prompt_fix_commit"],
        "status_doc_commit": git["status_doc_commit"],
        "freeze_commit": git["freeze_commit"],
        "agent_file_unchanged_since_agent_commit": git[
            "agent_file_unchanged_since_agent_commit"
        ],
        "frozen_assets_unchanged_since_freeze_commit": git[
            "frozen_assets_unchanged_since_freeze_commit"
        ],
        "commits_present": git["commits_present"],
        "git_head": git["head"],
        "prompt_version": PROMPT_VERSION,
        "prompt_status": manifest.get("status"),
        "active": manifest.get("active"),
        "runtime_active": manifest.get("runtime_active"),
        "default_prompt_version": settings.RAG_JUDGE_PROMPT_VERSION,
        "schema_version": manifest.get("schema_version"),
        "rubric_version": manifest.get("rubric_version"),
        "metric_version": METRIC_VERSION,
        "model": settings.DEFAULT_LLM_MODEL,
        "temperature": settings.DEFAULT_TEMPERATURE,
        "max_tokens": settings.RAG_JUDGE_MAX_TOKENS,
        "errors": errors,
        "application": application,
        "target": target,
        "labels": labels,
        "manifest": manifest,
        "validation": validation,
        "fixture": fixture,
    }


def patch_trace_for_case(
    recorder: CallRecorder,
    case_id: str,
    f_outcome: Any,
) -> dict[str, Any]:
    calls = recorder.for_case(case_id, "faithfulness")
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
    contract = (getattr(f_outcome, "details", {}) or {}).get("agent_contract") or {}
    return {
        "initial_output": primary.get("content") if primary else None,
        "patch_output": patch.get("content") if patch else None,
        "merged_output": getattr(f_outcome, "raw_output", None),
        "patch_call_index": patch.get("call_index") if patch else None,
        "patch_claim_ids": patch.get("patch_claim_ids") if patch else [],
        "patch_applied_claims": list(contract.get("patch_applied_claims") or []),
    }


def render_metrics_table(case: dict[str, Any]) -> list[str]:
    lines = [
        "| metric | status | score | skipped/invalid |",
        "|---|---|---:|---|",
    ]
    for name, payload in case["metrics"].items():
        lines.append(
            f"| {name} | {payload['status']} | {payload.get('score')} | "
            f"{payload.get('skipped_reason') or payload.get('invalid_reason') or '—'} |"
        )
    return lines


def render_calls_table(case: dict[str, Any]) -> list[str]:
    calls = case.get("calls") or {}
    return [
        "| 项 | 值 |",
        "|---|---:|",
        f"| calls | {calls.get('calls', 0)} |",
        f"| primary / patch / repair / retry | "
        f"{calls.get('primary', 0)} / {calls.get('patch', 0)} / "
        f"{calls.get('repair', 0)} / {calls.get('retry', 0)} |",
        f"| input / output tokens | {calls.get('input_tokens', 0)} / "
        f"{calls.get('output_tokens', 0)} |",
        f"| cost CNY | {calls.get('cost_cny', 0):.6f} |",
    ]


def render_claims_table(claims: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| claim_id | claim | type | subtype | support | contradictory | evidence quotes |",
        "|---|---|---|---|---|---|---|",
    ]
    for claim in claims:
        quotes = [
            str(ref.get("quote") or "") for ref in (claim.get("evidence_refs") or [])
        ]
        lines.append(
            f"| {claim.get('claim_id')} | {claim.get('claim')} | "
            f"{claim.get('claim_type')} | {claim.get('claim_subtype')} | "
            f"{claim.get('support_status')} | {claim.get('is_contradictory')} | "
            f"{json.dumps(quotes, ensure_ascii=False)} |"
        )
    return lines


def render_case(case: dict[str, Any]) -> list[str]:
    checks_for_line = {
        key: value
        for key, value in (case.get("checks") or {}).items()
        if key not in {"agent_contract", "claims"}
    }
    lines = [
        f"### {case['case_id']} — {case['status']}",
        "",
        f"- targets：`{case['targets']}`",
        f"- checks：`{json.dumps(checks_for_line, ensure_ascii=False)}`",
        "",
    ]
    lines.extend(render_metrics_table(case))
    lines.extend(["", "调用与成本：", ""])
    lines.extend(render_calls_table(case))
    lines.append("")
    claims = case.get("claims") or []
    if claims:
        lines.append("claim 级明细：")
        lines.append("")
        lines.extend(render_claims_table(claims))
        lines.append("")
    agent_contract = case.get("agent_contract")
    if agent_contract:
        lines.extend(
            [
                "F agent_contract：",
                "",
                "```json",
                json.dumps(agent_contract, ensure_ascii=False, indent=1),
                "```",
                "",
            ]
        )
    c_contract = case.get("c_contract")
    if c_contract:
        lines.extend(
            [
                "C agent_contract：",
                "",
                "```json",
                json.dumps(c_contract, ensure_ascii=False, indent=1),
                "```",
                "",
            ]
        )
    if case["case_id"] == "Q23":
        lines.extend(render_q23_details(case))
    elif case["case_id"] == "Q21":
        lines.extend(render_q21_details(case))
    elif case["case_id"] == "Q11":
        lines.extend(render_q11_details(case))
    return lines


def render_q23_details(case: dict[str, Any]) -> list[str]:
    checks = case.get("checks") or {}
    trace = case.get("patch_trace") or {}
    lines = [
        "Q23 patch 三段输出：",
        "",
        f"- patch_triggered：`{checks.get('patch_triggered')}`",
        f"- patch_applied_claims：`{checks.get('patch_applied_claims')}`",
        f"- patch_semantic_review_required："
        f"`{checks.get('patch_semantic_review_required')}`",
        f"- absence 四字段：`{json.dumps(checks.get('absence_fields'), ensure_ascii=False)}`",
        f"- cl5 / mixed_sentence_warnings："
        f"`{json.dumps(checks.get('mixed_sentence_warnings'), ensure_ascii=False)}`",
        f"- patch_review：`{json.dumps(checks.get('patch_review'), ensure_ascii=False)}`",
        "",
        "初始输出：",
        "",
        "```json",
        str(trace.get("initial_output") or ""),
        "```",
        "",
        "patch 输出：",
        "",
        "```json",
        str(trace.get("patch_output") or ""),
        "```",
        "",
        "merged 输出：",
        "",
        "```json",
        str(trace.get("merged_output") or ""),
        "```",
        "",
    ]
    return lines


def render_q21_details(case: dict[str, Any]) -> list[str]:
    checks = case.get("checks") or {}
    lines = [
        "Q21 豁免 claim 明细：",
        "",
        "```json",
        json.dumps(checks.get("exemption_claims"), ensure_ascii=False, indent=1),
        "```",
        "",
        f"- F score：`{checks.get('f_score')}`；F=1.0：`{checks.get('f_is_one')}`",
        f"- semantic_pass：`{checks.get('semantic_pass')}`；"
        f"semantic_pass_target_miss：`{checks.get('semantic_pass_target_miss')}`",
        "",
    ]
    return lines


def render_q11_details(case: dict[str, Any]) -> list[str]:
    checks = case.get("checks") or {}
    lines = [
        "Q11 quote 连续性：",
        "",
        "| claim_id | context_id | quote | contiguous | ellipsis |",
        "|---|---|---|---|---|",
    ]
    for item in checks.get("quote_checks") or []:
        lines.append(
            f"| {item.get('claim_id')} | {item.get('context_id')} | "
            f"{item.get('quote')} | {item.get('contiguous_substring')} | "
            f"{item.get('has_ellipsis')} |"
        )
    lines.extend(
        [
            "",
            f"- target_pass：`{checks.get('target_pass')}`",
            f"- quote_pass：`{checks.get('quote_pass')}`",
            "",
        ]
    )
    return lines


def build_stop_conditions(
    results: dict[str, Any],
    *,
    ledger_errors: list[str],
) -> list[dict[str, Any]]:
    cases = {case["case_id"]: case for case in results.get("cases") or []}
    metrics = [
        metric
        for case in results.get("cases") or []
        for metric in (case.get("metrics") or {}).values()
    ]
    checks = {case_id: case.get("checks") or {} for case_id, case in cases.items()}
    flags: dict[str, tuple[bool, str]] = {}
    flags["invalid_contract"] = (
        any(metric.get("status") in {"invalid", "failed"} for metric in metrics),
        "invalid/failed metric present",
    )
    q23 = cases.get("Q23") or {}
    q23_checks_data = checks.get("Q23") or {}
    q23_stop = set(q23_checks_data.get("stop_codes") or [])
    q23_contract = q23.get("agent_contract") or {}
    final_errors = q23_contract.get("final_errors") or []
    flags["schema_or_patch_failure"] = (
        bool(final_errors) or "schema_or_patch_failure" in q23_stop,
        f"Q23 final_errors={final_errors}",
    )
    patch_review = q23_checks_data.get("patch_review") or {}
    flags["q23_patch_semantic_change"] = (
        "q23_patch_semantic_change" in q23_stop,
        f"changed_outside_applied={patch_review.get('changed_outside_applied')}",
    )
    absence_fields = q23_checks_data.get("absence_fields") or []
    flags["q23_absence_contract"] = (
        "q23_absence_contract" in q23_stop,
        f"absence_fields={absence_fields}",
    )
    flags["q23_f_or_c_target"] = (
        "q23_f_or_c_target" in q23_stop,
        f"F={q23_checks_data.get('f_target_pass')}, "
        f"C={q23_checks_data.get('c_target_pass')}",
    )
    q21_checks_data = checks.get("Q21") or {}
    q21_stop = set(q21_checks_data.get("stop_codes") or [])
    flags["q21_semantic_or_f_one"] = (
        "q21_semantic_or_f_one" in q21_stop,
        f"F=1.0={q21_checks_data.get('f_is_one')}, "
        f"semantic_pass={q21_checks_data.get('semantic_pass')}",
    )
    q11_checks_data = checks.get("Q11") or {}
    q11_stop = set(q11_checks_data.get("stop_codes") or [])
    flags["q11_quote_or_target"] = (
        "q11_quote_or_target" in q11_stop,
        f"target_pass={q11_checks_data.get('target_pass')}, "
        f"quote_pass={q11_checks_data.get('quote_pass')}",
    )
    meta = results.get("meta") or {}
    flags["fingerprint_mismatch"] = (
        bool(meta.get("fingerprint_errors")),
        f"fingerprint_errors={meta.get('fingerprint_errors')}",
    )
    flags["budget_ceiling"] = (
        int(meta.get("total_judge_calls") or 0) > MAX_JUDGE_CALLS
        or float(meta.get("cost_cny") or 0.0) > CEILING_CNY
        or bool(meta.get("budget_error")),
        f"calls={meta.get('total_judge_calls')}, cost={meta.get('cost_cny')}, "
        f"budget_error={meta.get('budget_error')}",
    )
    missing_case = set(CASE_IDS) - set(cases)
    missing_metric = [
        f"{case['case_id']}:{name}"
        for case in results.get("cases") or []
        for name in ("faithfulness", "answer_correctness", "answer_relevancy")
        if name not in (case.get("metrics") or {})
    ]
    flags["ledger_or_missing_result"] = (
        bool(ledger_errors)
        or bool(meta.get("ledger_uncertain_calls"))
        or bool(missing_case)
        or bool(missing_metric),
        f"ledger_errors={ledger_errors}, uncertain={meta.get('ledger_uncertain_calls')}, "
        f"missing_cases={sorted(missing_case)}, missing_metrics={missing_metric}",
    )
    return [
        {
            "code": code,
            "condition": condition,
            "triggered": flags.get(code, (False, ""))[0],
            "evidence": flags.get(code, (False, ""))[1],
        }
        for code, condition in STOP_CONDITION_DEFS
    ]


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
                        "fixture",
                    }
                }
            },
            ensure_ascii=False,
            indent=1,
        ),
        flush=True,
    )
    application = preflight_result["application"]
    fixture = preflight_result["fixture"]
    by_id = {case["id"]: case for case in fixture["cases"]}
    app_by_id = {case["case_id"]: case for case in application["cases"]}
    recorder: CallRecorder | None = None
    effective: list[dict[str, Any]] = []
    ledger_errors: list[str] = []

    results: dict[str, Any] = {
        "meta": {
            "name": "m1d6-v1.2.4-single-case-diagnostic-results",
            "kind": "judge_only_production_service_replay_not_end_to_end",
            "date": "2026-11-23",
            "diagnostic_only": True,
            "counts_toward_10": False,
            "application_sha256": preflight_result["application_sha256"],
            "judge_run": True,
            "created_run": False,
            "wrote_db": False,
            "runtime_activated": False,
            "weknora_called": False,
            "rag_adapter_called": False,
            "ran_10": False,
            "ran_40": False,
            "default_prompt_version": preflight_result["default_prompt_version"],
            "prompt_version": PROMPT_VERSION,
            "prompt_status": preflight_result["prompt_status"],
            "prompt_sha256": preflight_result["prompt_sha256"],
            "manifest_sha256": preflight_result["manifest_sha256"],
            "validation_sha256": preflight_result["validation_sha256"],
            "leakage_audit_sha256": preflight_result["leakage_audit_sha256"],
            "leakage_findings": preflight_result["leakage_findings"],
            "leakage_source_count": preflight_result["leakage_source_count"],
            "fixture_sha256": preflight_result["fixture_sha256"],
            "target_sha256": preflight_result["target_sha256"],
            "labels_sha256": preflight_result["labels_sha256"],
            "patch_schema_sha256": preflight_result["patch_schema_sha256"],
            "patch_example_sha256": preflight_result["patch_example_sha256"],
            "quote_validator_sha256": preflight_result["quote_validator_sha256"],
            "ledger_file": preflight_result["ledger_file"],
            "ledger_initial_sha256": preflight_result["ledger_initial_sha256"],
            "ledger_self_test": preflight_result["ledger_self_test"],
            "agent_commit": preflight_result["agent_commit"],
            "initial_implementation_commit": preflight_result[
                "initial_implementation_commit"
            ],
            "patch_prompt_fix_commit": preflight_result["patch_prompt_fix_commit"],
            "status_doc_commit": preflight_result["status_doc_commit"],
            "freeze_commit": preflight_result["freeze_commit"],
            "git_head": preflight_result["git_head"],
            "rubric_version": RUBRIC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "metric_version": METRIC_VERSION,
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
                    "fixture",
                }
            },
        },
        "effective_prompt_versions": effective,
        "cases": [],
        "calls": [],
        "stop_triggered": False,
        "stop_reason": None,
        "stop_codes": [],
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
        results["stop_codes"] = ["fingerprint_mismatch", "ledger_or_missing_result"]
    else:
        try:
            ledger = LedgerWriter(
                LEDGER_FILE,
                EXPECTED_LEDGER_INITIAL_SHA,
                require_empty=True,
            )
        except LedgerError as exc:
            results["stop_triggered"] = True
            results["stop_reason"] = f"ledger: {exc}"
            results["stop_codes"] = ["ledger_or_missing_result"]
            ledger = None
        if ledger is not None:
            recorder = CallRecorder(ledger=ledger)
            async with LLMClient() as real_llm:

                def factory(metric: str) -> RagJudgeAgent:
                    loaded = load_judge_prompt(PROMPT_VERSION, metric)
                    loaded_sha = sha256_text(loaded)
                    expected_sha = {
                        "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
                        "answer_correctness": EXPECTED_PROMPT_SHA[
                            "answer_correctness.txt"
                        ],
                        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
                    }[metric]
                    if loaded_sha != expected_sha:
                        ledger_errors.append(
                            f"{context['case_id']}/{metric}: loaded prompt SHA {loaded_sha}"
                        )
                    effective.append(
                        {
                            "case_id": context["case_id"],
                            "metric": metric,
                            "prompt_version": PROMPT_VERSION,
                            "prompt_sha256": loaded_sha,
                            "expected_prompt_sha256": expected_sha,
                            "schema_version": SCHEMA_VERSION,
                            "metric_version": METRIC_VERSION,
                        }
                    )
                    print(
                        json.dumps(
                            {
                                "effective_prompt_version": PROMPT_VERSION,
                                "case_id": context["case_id"],
                                "metric": metric,
                                "prompt_sha256": loaded_sha,
                                "expected_prompt_sha256": expected_sha,
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
                    context = {"case_id": case_id}
                    app_case = app_by_id[case_id]
                    print(
                        json.dumps(
                            {
                                "starting_case": case_id,
                                "prompt_version": PROMPT_VERSION,
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
                    metrics = {
                        name: {
                            "status": outcome.status,
                            "score": outcome.score,
                            "skipped_reason": outcome.skipped_reason,
                            "invalid_reason": outcome.invalid_reason,
                        }
                        for name, outcome in outcomes_by_name.items()
                    }
                    case_result: dict[str, Any] = {
                        "case_id": case_id,
                        "group": app_case["group"],
                        "final_category": app_case["final_category"],
                        "targets": app_case["targets"],
                        "metrics": metrics,
                        "fingerprint_errors": fingerprint_errors,
                        "outcomes": [outcome_payload(outcome) for outcome in outcomes],
                        "claims": [],
                        "agent_contract": (
                            (getattr(f, "details", {}) or {}).get("agent_contract")
                            if f is not None
                            else None
                        ),
                        "c_contract": (
                            (getattr(c, "details", {}) or {}).get("agent_contract")
                            if c is not None
                            else None
                        ),
                        "calls": case_call_summary(recorder, case_id),
                    }

                    if fingerprint_errors:
                        results["stop_triggered"] = True
                        results[
                            "stop_reason"
                        ] = f"{case_id}: fingerprint: " + "; ".join(fingerprint_errors)
                        results["stop_codes"] = ["fingerprint_mismatch"]
                        case_result["status"] = "stopped"
                        case_result["checks"] = {
                            "passed": False,
                            "failures": fingerprint_errors,
                            "notes": [],
                            "stop_codes": ["fingerprint_mismatch"],
                        }
                    elif any(
                        outcome.status in {"invalid", "failed"} for outcome in outcomes
                    ):
                        bad = [
                            f"{outcome.metric_name}={outcome.status}"
                            f"({outcome.invalid_reason or outcome.error_type})"
                            for outcome in outcomes
                            if outcome.status in {"invalid", "failed"}
                        ]
                        results["stop_triggered"] = True
                        results["stop_reason"] = f"{case_id}: " + ", ".join(bad)
                        results["stop_codes"] = (
                            ["budget_ceiling"]
                            if recorder.budget_exceeded
                            else ["invalid_contract"]
                        )
                        case_result["status"] = "stopped"
                        case_result["checks"] = {
                            "passed": False,
                            "failures": bad,
                            "notes": [],
                            "stop_codes": results["stop_codes"],
                        }
                    elif case_id == "Q23":
                        patch_trace = patch_trace_for_case(recorder, case_id, f)
                        case_result["patch_trace"] = patch_trace
                        checks = q23_checks(f, strict, c, r, patch_trace=patch_trace)
                        case_result["checks"] = checks
                        case_result["claims"] = checks.pop("claims")
                        case_result["status"] = (
                            "passed" if checks["passed"] else "failed"
                        )
                        if not checks["passed"]:
                            results["stop_triggered"] = True
                            results["stop_reason"] = "Q23 contract: " + "; ".join(
                                checks["failures"]
                            )
                            results["stop_codes"] = checks["stop_codes"]
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
                            results["stop_codes"] = checks["stop_codes"] or [
                                "q21_semantic_or_f_one"
                            ]
                            results["gate"]["semantic_pass_target_miss"] = True
                        elif checks["passed"]:
                            case_result["status"] = "passed"
                        else:
                            case_result["status"] = "failed"
                            results["stop_triggered"] = True
                            results["stop_reason"] = "Q21 semantic: " + "; ".join(
                                checks["failures"]
                            )
                            results["stop_codes"] = checks["stop_codes"]
                    else:
                        checks = q11_checks(f, c, r, contexts)
                        case_result["checks"] = checks
                        case_result["claims"] = checks.pop("claims")
                        case_result["status"] = (
                            "passed" if checks["passed"] else "failed"
                        )
                        if not checks["passed"]:
                            results["stop_triggered"] = True
                            results["stop_reason"] = "Q11 regression: " + "; ".join(
                                checks["failures"]
                            )
                            results["stop_codes"] = checks["stop_codes"]

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

                    if (
                        recorder.budget_exceeded
                        or recorder.judge_calls > MAX_JUDGE_CALLS
                    ):
                        results["stop_triggered"] = True
                        results["stop_reason"] = (
                            f"budget: calls={recorder.judge_calls}, "
                            f"cost={recorder.cost:.6f}, error={ledger.budget_error}"
                        )
                        results["stop_codes"] = ["budget_ceiling"]
                    if results["stop_triggered"]:
                        break

            ledger_errors.extend(
                validate_ledger_fingerprint(
                    ledger,
                    effective,
                )
            )
            ledger_summary = ledger.summary()
            results["meta"].update(
                {
                    "ledger_sha256": ledger_summary["ledger_sha256"],
                    "ledger_total_attempts": ledger_summary["total_attempts"],
                    "ledger_finished_calls": ledger_summary["finished_calls"],
                    "ledger_uncertain_calls": ledger_summary["uncertain_calls"],
                    "ledger_started_by_kind": ledger_summary["started_by_kind"],
                    "ledger_finished_by_kind": ledger_summary["finished_by_kind"],
                    "ledger_by_case_metric": ledger_summary["by_case_metric"],
                    "total_judge_calls": ledger_summary["total_attempts"],
                    "cost_cny": ledger_summary["cost_cny"],
                    "ceiling_cny": CEILING_CNY,
                    "budget_error": ledger_summary["budget_error"],
                }
            )
            results["calls"] = recorder.calls
            if ledger.uncertain_calls:
                ledger_errors.append(f"uncertain_calls={ledger.uncertain_calls}")

    if recorder is None or "ledger_sha256" not in results["meta"]:
        results["meta"].update(
            {
                "ledger_sha256": None,
                "ledger_total_attempts": 0,
                "ledger_finished_calls": 0,
                "ledger_uncertain_calls": 0,
                "ledger_started_by_kind": {},
                "ledger_finished_by_kind": {},
                "ledger_by_case_metric": {},
                "total_judge_calls": 0,
                "cost_cny": 0.0,
                "ceiling_cny": CEILING_CNY,
                "budget_error": None,
            }
        )

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

    fingerprint_errors = [
        error
        for case in results["cases"]
        for error in case.get("fingerprint_errors") or []
    ]
    missing_results = [
        f"{case_id}:{metric}"
        for case_id in CASE_IDS
        for metric in ("faithfulness", "answer_correctness", "answer_relevancy")
        if not any(
            case["case_id"] == case_id and metric in case["metrics"]
            for case in results["cases"]
        )
    ]
    ledger_problems = list(ledger_errors)
    if results["meta"].get("ledger_sha256") is None:
        ledger_problems.append("ledger not initialized")
    if results["meta"].get("ledger_uncertain_calls"):
        ledger_problems.append(
            f"uncertain_calls={results['meta'].get('ledger_uncertain_calls')}"
        )
    if missing_results:
        ledger_problems.append(f"missing_results={missing_results}")
    results["meta"]["fingerprint_errors"] = fingerprint_errors
    results["meta"]["missing_results"] = missing_results
    results["meta"]["ledger_errors"] = ledger_problems
    results["stop_conditions"] = build_stop_conditions(
        results,
        ledger_errors=ledger_problems,
    )
    if any(item["triggered"] for item in results["stop_conditions"]):
        results["stop_triggered"] = True
    gate_passed = not failures and not results["stop_triggered"] and not ledger_problems
    results["gate"] = {
        "passed": gate_passed,
        "verified": gate_passed,
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
    results["meta"]["totals"] = call_summary(recorder) if recorder else {}

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

    lines = [
        "# M1-D-6 v1.2.4 单案例诊断结果（Q23 / Q21 / Q11）",
        "",
        f"> 状态：`{results['meta']['status']}`；diagnostic only；"
        "未创建 Run、未写 DB、未激活 v1.2.4。",
        f"> application SHA：`{preflight_result['application_sha256']}`",
        f"> ledger SHA：`{results['meta'].get('ledger_sha256') or '—'}`；"
        f"total attempts：`{results['meta'].get('ledger_total_attempts')}`；"
        f"uncertain calls：`{results['meta'].get('ledger_uncertain_calls')}`",
        f"> 结果 JSON SHA：`{json_sha}`",
        f"> Prompt：`{PROMPT_VERSION}` / `{preflight_result['prompt_status']}` / "
        f"F `{EXPECTED_PROMPT_SHA['faithfulness.txt']}`",
        f"> rubric：`{RUBRIC_VERSION}`；schema：`{SCHEMA_VERSION}`；"
        f"metric：`{METRIC_VERSION}`",
        f"> MANIFEST：`{preflight_result['manifest_sha256']}`；"
        f"validation：`{preflight_result['validation_sha256']}`",
        f"> patch schema：`{preflight_result['patch_schema_sha256']}`；"
        f"patch example：`{preflight_result['patch_example_sha256']}`；"
        f"quote validator：`{preflight_result['quote_validator_sha256']}`",
        f"> leakage audit：`{preflight_result['leakage_audit_sha256']}`；"
        f"findings={preflight_result['leakage_findings']}；"
        f"source_count={preflight_result['leakage_source_count']}",
        f"> fixture：`{preflight_result['fixture_sha256']}`；"
        f"target：`{preflight_result['target_sha256']}`；"
        f"labels：`{preflight_result['labels_sha256']}`",
        f"> agent_commit：`{preflight_result['agent_commit']}`；"
        f"initial：`{preflight_result['initial_implementation_commit']}`；"
        f"patch prompt fix：`{preflight_result['patch_prompt_fix_commit']}`；"
        f"status doc：`{preflight_result['status_doc_commit']}`；"
        f"freeze：`{preflight_result['freeze_commit']}`",
        f"> git HEAD：`{preflight_result['git_head']}`",
        "",
        "## 1. 运行时指纹",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 生效 Prompt 版本 | `{PROMPT_VERSION}`（显式传参；默认仍 `v1.0.0`） |",
        f"| F SHA | `{EXPECTED_PROMPT_SHA['faithfulness.txt']}` |",
        f"| C SHA | `{EXPECTED_PROMPT_SHA['answer_correctness.txt']}` |",
        f"| R SHA | `{EXPECTED_PROMPT_SHA['answer_relevancy.txt']}` |",
        f"| MANIFEST / validation | `{preflight_result['manifest_sha256']}` / "
        f"`{preflight_result['validation_sha256']}` |",
        f"| patch schema / example | `{preflight_result['patch_schema_sha256']}` / "
        f"`{preflight_result['patch_example_sha256']}` |",
        f"| quote validator | `{preflight_result['quote_validator_sha256']}` |",
        f"| leakage audit | `{preflight_result['leakage_audit_sha256']}`；"
        f"findings={preflight_result['leakage_findings']}；"
        f"source_count={preflight_result['leakage_source_count']} |",
        f"| fixture / target / labels | `{preflight_result['fixture_sha256']}` / "
        f"`{preflight_result['target_sha256']}` / "
        f"`{preflight_result['labels_sha256']}` |",
        f"| agent_commit / freeze_commit | `{preflight_result['agent_commit']}` / "
        f"`{preflight_result['freeze_commit']}` |",
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
        "| Case | F | F_strict | C | R | target | status | calls | cost CNY |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|",
    ]
    for case in results["cases"]:
        metrics = case["metrics"]
        f = metrics.get("faithfulness", {})
        fs = metrics.get("faithfulness_strict", {})
        c = metrics.get("answer_correctness", {})
        r = metrics.get("answer_relevancy", {})
        checks = case.get("checks") or {}
        target = "pass" if checks.get("target_pass") is not False else "miss"
        calls = case.get("calls") or {}
        lines.append(
            f"| {case['case_id']} | {f.get('score', f.get('status'))} | "
            f"{fs.get('score', fs.get('status'))} | {c.get('score', c.get('status'))} | "
            f"{r.get('score', r.get('status'))} | {target} | {case['status']} | "
            f"{calls.get('calls', 0)} | {calls.get('cost_cny', 0):.6f} |"
        )
    lines.extend(["", "## 3. 逐案例明细", ""])
    for case in results["cases"]:
        lines.extend(render_case(case))
        lines.append("")
    lines.extend(
        [
            "## 4. 调用、成本与 Ledger",
            "",
            "| 项 | 实际 | 预算/上限 |",
            "|---|---:|---:|",
            f"| Judge calls（ledger attempts） | "
            f"{results['meta'].get('ledger_total_attempts', 0)} | {MAX_JUDGE_CALLS} |",
            f"| primary | {results['meta'].get('totals', {}).get('primary_calls', 0)} | 9 |",
            f"| patch | {results['meta'].get('totals', {}).get('patch_calls', 0)} | 3 |",
            f"| repair | {results['meta'].get('totals', {}).get('repair_calls', 0)} | — |",
            f"| retry | {results['meta'].get('totals', {}).get('retry_calls', 0)} | 2 |",
            f"| input tokens | {results['meta'].get('totals', {}).get('input_tokens', 0)} | — |",
            f"| output tokens | {results['meta'].get('totals', {}).get('output_tokens', 0)} | — |",
            f"| Judge cost CNY | {results['meta'].get('cost_cny', 0):.6f} | "
            f"{CEILING_CNY:.2f} |",
            f"| ledger SHA | `{results['meta'].get('ledger_sha256') or '—'}` | — |",
            f"| uncertain calls | `{results['meta'].get('ledger_uncertain_calls', 0)}` | 0 |",
            "| ledger self-test | `",
            f"{json.dumps(preflight_result['ledger_self_test'], ensure_ascii=False)}",
            "` | — |",
            "",
            "## 5. 停止条件",
            "",
            "| code | condition | triggered | evidence |",
            "|---|---|---|---|",
        ]
    )
    for item in results["stop_conditions"]:
        lines.append(
            f"| `{item['code']}` | {item['condition']} | "
            f"`{item['triggered']}` | {item['evidence']} |"
        )
    lines.extend(
        [
            "",
            f"- stop_triggered：`{results['stop_triggered']}`",
            f"- stop_reason：{results['stop_reason'] or '—'}",
            f"- stop_codes：`{results['stop_codes']}`",
            f"- gate passed：`{results['gate']['passed']}`",
            f"- gate verified：`{results['gate']['verified']}`",
            f"- semantic_pass_target_miss："
            f"`{results['gate']['semantic_pass_target_miss']}`",
            f"- gate failures：{results['gate']['failures'] or '—'}",
            f"- gate notes：{results['gate']['notes'] or '—'}",
            "",
            "## 6. 交付声明",
            "",
            "- diagnostic only；不是 10 条，也不是 40 条；不计入 10 条样本。",
            "- 未创建 `RagEvaluationRun`、未写 DB、未调用 WeKnora/RAG adapter。",
            "- 未激活 v1.2.4；active/runtime_active 保持 false；默认仍 `v1.0.0`。",
            "- 未跑 10/40；单案例通过后才可重新提交 10 条申请。",
            "- 结论只使用 implemented / verified / blocked；未写 accepted。",
            "",
            "## 7. 原始输出（最终）",
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
                "stop_codes": results["stop_codes"],
                "gate": results["gate"],
                "totals": results["meta"]["totals"],
                "ledger_sha256": results["meta"].get("ledger_sha256"),
                "ledger_total_attempts": results["meta"].get("ledger_total_attempts"),
                "ledger_uncertain_calls": results["meta"].get("ledger_uncertain_calls"),
                "json_sha256": json_sha,
                "md_sha256": md_sha,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


def validate_ledger_fingerprint(
    ledger: LedgerWriter,
    effective: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    expected_by_metric = {
        "faithfulness": EXPECTED_PROMPT_SHA["faithfulness.txt"],
        "answer_correctness": EXPECTED_PROMPT_SHA["answer_correctness.txt"],
        "answer_relevancy": EXPECTED_PROMPT_SHA["answer_relevancy.txt"],
    }
    for record in ledger.started_records():
        kind = str(record.get("kind") or "primary")
        if kind in {"primary", "retry"}:
            metric = str(record.get("metric") or "")
            expected = expected_by_metric.get(metric)
            if expected and record.get("system_prompt_sha256") != expected:
                errors.append(
                    f"{record.get('case_id')}/{metric}/{kind}: "
                    f"system_prompt_sha256={record.get('system_prompt_sha256')!r}"
                )
    for item in effective:
        if item["prompt_sha256"] != item["expected_prompt_sha256"]:
            errors.append(
                f"effective {item['case_id']}/{item['metric']}: "
                f"prompt_sha256={item['prompt_sha256']!r}"
            )
    return sorted(set(errors))


if __name__ == "__main__":
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
                        "fixture",
                    }
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        raise SystemExit(1 if result["errors"] else 0)
    asyncio.run(main())
