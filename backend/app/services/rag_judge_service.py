"""RAG Judge 编排服务（Phase 3B）。

职责：给定一条 ``RagTrace``（+ 可选的 ``QaDatasetItem``），产出三个指标的
``JudgeOutcome`` 列表。**不落库、不调度**（Phase 3C 负责持久化与批量）。

硬约束：
- Faithfulness 只使用 Trace 的真实生成上下文（``context_source="agent_chat"``）；
  上下文不可用 → ``skipped(context_unavailable)``，**不调用模型**；
- Faithfulness 的 score 由代码按 claims 计算；claims 为空 → ``skipped(no_claims)``（不是 1.0）；
- 任何指标失败不影响其它指标，也不修改 Trace / 检索结果。
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rag_judge_agent import RagJudgeAgent, resolve_prompt_version
from app.models import QaDatasetItem, RagTrace
from app.schemas.agents.rag_judge import (
    JUDGE_SCHEMA_V1,
    JUDGE_SCHEMA_V2,
    RAG_JUDGE_METRICS,
    RagJudgeMetric,
    judge_schema_version,
    metric_version_for_prompt,
)

JudgeStatus = Literal["evaluated", "skipped", "failed"]

# 上下文与原始输出上限：避免把超长 Trace 原样塞进 Prompt / 结果
MAX_CONTEXTS = 20
MAX_CONTEXT_CHARS = 6000
MAX_RAW_CHARS = 20000

SUPPORT_STATUSES = {"supported", "unsupported", "insufficient_evidence"}
CLAIM_TYPES = {"factual_claim", "non_factual"}
FACTUAL_SUBTYPES = {"policy", "conflict"}
NON_FACTUAL_SUBTYPES = {"absence", "advice", "meta"}

AgentFactory = Callable[[RagJudgeMetric], RagJudgeAgent]


@dataclass(frozen=True)
class JudgeOutcome:
    """单指标评测结果（3C 落库的输入结构）。"""

    metric_name: str
    metric_version: str
    status: JudgeStatus
    score: float | None = None
    skipped_reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    judge_config: dict[str, Any] = field(default_factory=dict)
    raw_output: str | None = None
    raw_truncated: bool = False
    latency_ms: int = 0
    error_message: str | None = None


def _truncate_raw(text: str | None) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    if len(text) <= MAX_RAW_CHARS:
        return text, False
    return text[:MAX_RAW_CHARS], True


def _contexts_from_trace(trace: RagTrace) -> list[str]:
    contexts: list[str] = []
    for item in trace.retrieved_contexts or []:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        contexts.append(content[:MAX_CONTEXT_CHARS])
        if len(contexts) >= MAX_CONTEXTS:
            break
    return contexts


def _answer_of(trace: RagTrace) -> str:
    return (trace.answer or "").strip()


def _gold_answer_of(item: QaDatasetItem | None) -> str:
    if item is None:
        return ""
    return (item.gold_answer or "").strip()


def _skip_reason(
    metric: RagJudgeMetric,
    *,
    trace: RagTrace,
    contexts: Sequence[str],
    gold_answer: str,
) -> str | None:
    if trace.status != "success":
        return "trace_failed"
    answer = _answer_of(trace)
    if metric == "faithfulness":
        if trace.context_source != "agent_chat" or not contexts:
            return "context_unavailable"
        if not answer:
            return "answer_missing"
        return None
    if metric == "answer_correctness":
        if not answer:
            return "answer_missing"
        if not gold_answer:
            return "gold_answer_missing"
        return None
    if not answer:
        return "answer_missing"
    return None


def _judge_config(agent: RagJudgeAgent, *, model: str | None) -> dict[str, Any]:
    return {
        "agent": agent.config.name,
        "model": model,
        "temperature": agent.config.temperature,
        "max_tokens": agent.config.max_tokens,
        "prompt_version": getattr(agent, "prompt_version", agent.config.version),
        "resolved_prompt_version": getattr(agent, "prompt_version", agent.config.version),
        "prompt_sha256": agent.prompt_sha256,
        "schema_version": getattr(agent, "schema_version", JUDGE_SCHEMA_V1),
        "rubric_version": getattr(agent, "rubric_version", agent.config.version),
        "metric_version": agent.metric_version,
    }


def _usage_details(result: Any) -> dict[str, Any]:
    """Phase 3E：把真实调用的 token/成本随结果带出（details 落库，不改表结构）。"""
    return {
        "token_usage": dict(getattr(result, "token_usage", None) or {}),
        "cost": str(getattr(result, "cost", "") or "0"),
    }


def _payload(
    metric: RagJudgeMetric,
    *,
    trace: RagTrace,
    contexts: Sequence[str],
    gold_answer: str,
) -> dict[str, Any]:
    base = {"query": trace.query, "answer": trace.answer or ""}
    if metric == "faithfulness":
        return {**base, "contexts": list(contexts)}
    if metric == "answer_correctness":
        return {**base, "gold_answer": gold_answer}
    return base


def _skipped(
    metric: RagJudgeMetric,
    reason: str,
    *,
    model: str | None = None,
    prompt_version: str | None = None,
) -> JudgeOutcome:
    version = resolve_prompt_version(prompt_version)
    schema_version = judge_schema_version(version)
    metric_version = metric_version_for_prompt(metric, version)
    return JudgeOutcome(
        metric_name=metric,
        metric_version=metric_version,
        status="skipped",
        skipped_reason=reason,
        judge_config={
            "agent": f"rag_judge_{metric}",
            "model": model,
            "prompt_version": version,
            "resolved_prompt_version": version,
            "schema_version": schema_version,
            "rubric_version": version,
            "metric_version": metric_version,
        },
    )


def _validation_error(claim_id: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"claim_id": claim_id, "code": code, "message": message, **extra}


def _normalize_v2_claim(
    raw: dict[str, Any], index: int, errors: list[dict[str, Any]]
) -> dict[str, Any]:
    """v1.1.1 claim 归一化：非法字段记 validation_error，不静默当 supported。"""
    claim = dict(raw)
    claim_id = str(claim.get("claim_id") or f"cl{index}")
    if not claim.get("claim_id"):
        errors.append(_validation_error(claim_id, "missing_claim_id", "claim_id is required"))
    claim["claim_id"] = claim_id

    raw_type = claim.get("claim_type")
    if raw_type not in CLAIM_TYPES:
        errors.append(
            _validation_error(
                claim_id,
                "claim_type_invalid",
                "claim_type must be factual_claim/non_factual",
                value=raw_type,
            )
        )
        claim_type = "factual_claim"
    else:
        claim_type = raw_type
    claim["claim_type"] = claim_type

    raw_subtype = claim.get("claim_subtype")
    allowed_subtypes = FACTUAL_SUBTYPES if claim_type == "factual_claim" else NON_FACTUAL_SUBTYPES
    if raw_subtype not in allowed_subtypes:
        known_subtype = raw_subtype in (FACTUAL_SUBTYPES | NON_FACTUAL_SUBTYPES)
        errors.append(
            _validation_error(
                claim_id,
                "claim_subtype_type_mismatch" if known_subtype else "claim_subtype_invalid",
                f"claim_subtype {raw_subtype!r} is not valid for {claim_type}",
                value=raw_subtype,
            )
        )
        subtype = "policy" if claim_type == "factual_claim" else "meta"
    else:
        subtype = raw_subtype
    claim["claim_subtype"] = subtype

    raw_status = claim.get("support_status")
    legacy_supported = claim.get("supported")
    if claim_type == "non_factual":
        if raw_status is not None:
            errors.append(
                _validation_error(
                    claim_id,
                    "non_factual_support_status",
                    "non_factual claim must not have support_status",
                    value=raw_status,
                )
            )
        claim["support_status"] = None
    else:
        if raw_status not in SUPPORT_STATUSES:
            errors.append(
                _validation_error(
                    claim_id,
                    "support_status_invalid",
                    "factual claim requires support_status",
                    value=raw_status,
                )
            )
            status = "insufficient_evidence"
        else:
            status = raw_status
        if (
            raw_status in SUPPORT_STATUSES
            and isinstance(legacy_supported, bool)
            and legacy_supported != (raw_status == "supported")
        ):
            errors.append(
                _validation_error(
                    claim_id,
                    "legacy_supported_conflict",
                    "supported bool conflicts with support_status",
                    supported=legacy_supported,
                    support_status=raw_status,
                )
            )
        claim["support_status"] = status

    if not isinstance(claim.get("is_contradictory"), bool):
        errors.append(
            _validation_error(
                claim_id,
                "is_contradictory_invalid",
                "is_contradictory must be boolean",
                value=claim.get("is_contradictory"),
            )
        )
        claim["is_contradictory"] = False

    raw_pair = claim.get("contradiction_with")
    if raw_pair is None:
        claim["contradiction_with"] = []
    elif not isinstance(raw_pair, list):
        errors.append(
            _validation_error(
                claim_id,
                "contradiction_with_invalid",
                "contradiction_with must be a list",
            )
        )
        claim["contradiction_with"] = []
    else:
        claim["contradiction_with"] = [str(item) for item in raw_pair]
    return claim


def _validate_v2_evidence(
    claim: dict[str, Any],
    context_map: dict[str, str],
    errors: list[dict[str, Any]],
    evidence_checks: list[dict[str, Any]],
) -> bool:
    """校验逐字证据；supported 失败时降级为 insufficient_evidence。"""
    claim_id = claim["claim_id"]
    raw_refs = claim.get("evidence_refs")
    if raw_refs is None:
        refs: list[Any] = []
    elif not isinstance(raw_refs, list):
        errors.append(
            _validation_error(claim_id, "evidence_refs_invalid", "evidence_refs must be a list")
        )
        refs = []
    else:
        refs = raw_refs

    normalized_refs: list[dict[str, str]] = []
    refs_ok = True
    for raw_ref in refs:
        if not isinstance(raw_ref, dict):
            errors.append(
                _validation_error(
                    claim_id, "evidence_ref_invalid", "evidence_ref must be an object"
                )
            )
            refs_ok = False
            continue
        context_id = str(raw_ref.get("context_id") or "")
        quote = str(raw_ref.get("quote") or "")
        normalized_refs.append({"context_id": context_id, "quote": quote})
        check = {
            "claim_id": claim_id,
            "context_id": context_id,
            "quote": quote,
            "ok": True,
            "error": None,
        }
        if not context_id or context_id not in context_map:
            check.update(ok=False, error="unknown_context_id")
            errors.append(
                _validation_error(
                    claim_id,
                    "unknown_context_id",
                    "evidence context_id is not in C1..Cn",
                    context_id=context_id,
                )
            )
            refs_ok = False
        elif not quote.strip():
            check.update(ok=False, error="empty_quote")
            errors.append(_validation_error(claim_id, "empty_quote", "evidence quote is empty"))
            refs_ok = False
        elif quote.strip() not in context_map[context_id].strip():
            check.update(ok=False, error="quote_not_found")
            errors.append(
                _validation_error(
                    claim_id,
                    "quote_not_found",
                    "evidence quote is not a verbatim substring",
                    context_id=context_id,
                )
            )
            refs_ok = False
        evidence_checks.append(check)
    claim["evidence_refs"] = normalized_refs

    if claim["claim_type"] == "factual_claim" and claim["support_status"] == "supported":
        if not refs:
            claim["support_status"] = "insufficient_evidence"
            errors.append(
                _validation_error(
                    claim_id,
                    "supported_without_evidence",
                    "supported claim requires at least one evidence_ref",
                )
            )
            return True
        if not refs_ok:
            claim["support_status"] = "insufficient_evidence"
            errors.append(
                _validation_error(
                    claim_id,
                    "evidence_validation_failed",
                    "supported claim has invalid evidence; downgraded",
                )
            )
            return True
    if claim["claim_subtype"] == "conflict" and claim["support_status"] == "supported":
        distinct_keys = {(ref["context_id"], ref["quote"].strip()) for ref in normalized_refs}
        distinct_quotes = {key[1] for key in distinct_keys}
        has_substring_pair = any(
            left != right and (left in right or right in left)
            for left in distinct_quotes
            for right in distinct_quotes
        )
        if len(distinct_keys) < 2 or len(distinct_quotes) < 2 or has_substring_pair:
            claim["support_status"] = "insufficient_evidence"
            errors.append(
                _validation_error(
                    claim_id,
                    "conflict_single_sided_evidence",
                    "conflict claim needs two distinct, non-nested quotes; downgraded",
                )
            )
            return True
    return False


def _validate_v2_contradictions(claims: list[dict[str, Any]], errors: list[dict[str, Any]]) -> None:
    by_id = {claim["claim_id"]: claim for claim in claims}
    factual_ids = {claim["claim_id"] for claim in claims if claim["claim_type"] == "factual_claim"}
    for claim in claims:
        claim_id = claim["claim_id"]
        if claim["claim_subtype"] == "conflict" and claim["is_contradictory"]:
            errors.append(
                _validation_error(
                    claim_id,
                    "conflict_marked_contradictory",
                    "document conflict must not be answer-internal contradiction",
                )
            )
            claim["is_contradictory"] = False
            claim["contradiction_with"] = []
            continue
        if not claim["is_contradictory"]:
            if claim["contradiction_with"]:
                errors.append(
                    _validation_error(
                        claim_id,
                        "contradiction_with_without_flag",
                        "contradiction_with requires is_contradictory=true",
                    )
                )
                claim["contradiction_with"] = []
            continue

        valid = True
        if claim["claim_type"] != "factual_claim":
            errors.append(
                _validation_error(
                    claim_id,
                    "non_factual_contradictory",
                    "only factual claims can be contradictory",
                )
            )
            valid = False
        if not claim["contradiction_with"]:
            errors.append(
                _validation_error(
                    claim_id,
                    "missing_contradiction_pair",
                    "is_contradictory requires contradiction_with",
                )
            )
            valid = False
        if claim_id in claim["contradiction_with"]:
            errors.append(
                _validation_error(
                    claim_id,
                    "self_contradiction",
                    "contradiction_with must not self-reference",
                )
            )
            valid = False
        for other in claim["contradiction_with"]:
            target = by_id.get(other)
            if target is None:
                errors.append(
                    _validation_error(
                        claim_id,
                        "unknown_contradiction_pair",
                        "contradiction_with references an unknown claim",
                        other=other,
                    )
                )
                valid = False
            elif target["claim_type"] != "factual_claim":
                errors.append(
                    _validation_error(
                        claim_id,
                        "non_factual_contradiction_pair",
                        "contradiction_with must reference factual claims",
                        other=other,
                    )
                )
                valid = False
        if len(factual_ids) < 2:
            errors.append(
                _validation_error(
                    claim_id,
                    "insufficient_contradiction_claims",
                    "answer-internal contradiction needs >=2 factual claims",
                )
            )
            valid = False
        if not valid:
            claim["is_contradictory"] = False
            claim["contradiction_with"] = []


def _faithfulness_score(
    data: dict[str, Any],
    *,
    contexts: Sequence[str] = (),
    schema_version: str = JUDGE_SCHEMA_V1,
) -> tuple[float | None, dict[str, Any], str | None]:
    """返回 ``(score, details, skipped_reason)``。

    v1.0.0：全部 claims 进分母，``supported`` 为事实源（行为不变）；
    v1.1.1：``factual_claim`` 进分母，non_factual 不进；0 scorable → skipped。
    """
    claims = list(data.get("claims") or [])
    if schema_version != JUDGE_SCHEMA_V2:
        total = len(claims)
        if total == 0:
            return None, {"claims": [], "reason": data.get("reason") or ""}, "no_claims"
        supported_count = sum(1 for claim in claims if claim.get("supported"))
        return (
            round(supported_count / total, 6),
            {
                "claims": claims,
                "supported_count": supported_count,
                "claim_count": total,
                "reason": data.get("reason") or "",
            },
            None,
        )

    context_map = {f"C{index}": str(content) for index, content in enumerate(contexts, 1)}
    validation_errors: list[dict[str, Any]] = []
    evidence_checks: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    evidence_failed = False
    seen_claim_ids: set[str] = set()
    for index, raw in enumerate(claims, 1):
        if not isinstance(raw, dict):
            validation_errors.append(
                _validation_error(f"cl{index}", "claim_invalid", "claim must be an object")
            )
            continue
        claim = _normalize_v2_claim(raw, index, validation_errors)
        if claim["claim_id"] in seen_claim_ids:
            validation_errors.append(
                _validation_error(
                    claim["claim_id"],
                    "duplicate_claim_id",
                    "claim_id must be unique within one answer; duplicate skipped",
                )
            )
            continue
        seen_claim_ids.add(claim["claim_id"])
        downgraded = _validate_v2_evidence(claim, context_map, validation_errors, evidence_checks)
        evidence_failed = evidence_failed or downgraded
        normalized.append(claim)
    _validate_v2_contradictions(normalized, validation_errors)

    scorable = [claim for claim in normalized if claim["claim_type"] == "factual_claim"]
    supported = [claim for claim in scorable if claim["support_status"] == "supported"]
    unsupported = [claim for claim in scorable if claim["support_status"] == "unsupported"]
    insufficient = [
        claim for claim in scorable if claim["support_status"] == "insufficient_evidence"
    ]
    non_factual = [claim for claim in normalized if claim["claim_type"] == "non_factual"]
    absence = [claim for claim in normalized if claim["claim_subtype"] == "absence"]
    document_conflicts = [
        claim
        for claim in normalized
        if claim["claim_subtype"] == "conflict" and claim["support_status"] == "supported"
    ]
    contradictions = [claim for claim in scorable if claim["is_contradictory"]]
    details: dict[str, Any] = {
        "claims": normalized,
        "reason": data.get("reason") or "",
        "claim_count": len(normalized),
        "scorable_claim_count": len(scorable),
        "supported_count": len(supported),
        "supported_claim_count": len(supported),
        "unsupported_claim_count": len(unsupported),
        "insufficient_evidence_count": len(insufficient),
        "non_factual_count": len(non_factual),
        "absence_count": len(absence),
        "document_conflict": bool(document_conflicts),
        "document_conflict_count": len(document_conflicts),
        "contradiction_count": len(contradictions),
        "insufficient_evidence_rate": (
            round(len(insufficient) / len(scorable), 6) if scorable else None
        ),
        "all_insufficient": bool(scorable) and len(insufficient) == len(scorable),
        "evidence_validation": evidence_checks,
        "evidence_validation_failed": evidence_failed,
        "validation_errors": validation_errors,
    }
    if not scorable:
        return None, details, "no_scorable_claims"
    return round(len(supported) / len(scorable), 6), details, None


async def judge_trace(
    session: AsyncSession | None,
    *,
    trace: RagTrace,
    item: QaDatasetItem | None = None,
    metrics: Sequence[RagJudgeMetric] | None = None,
    agent_factory: AgentFactory | None = None,
    prompt_version: str | None = None,
    schema_version: str | None = None,
) -> list[JudgeOutcome]:
    """对一条 Trace 执行指定指标；返回按 ``RAG_JUDGE_METRICS`` 顺序排列的结果。"""
    requested = list(metrics or RAG_JUDGE_METRICS)
    unknown = [metric for metric in requested if metric not in RAG_JUDGE_METRICS]
    if unknown:
        raise ValueError(f"unknown rag judge metrics: {unknown}")

    resolved_prompt_version = resolve_prompt_version(prompt_version)
    resolved_schema_version = schema_version or judge_schema_version(resolved_prompt_version)
    contexts = _contexts_from_trace(trace)
    gold_answer = _gold_answer_of(item)
    factory: AgentFactory = agent_factory or (
        lambda metric: RagJudgeAgent(metric, prompt_version=resolved_prompt_version)
    )

    outcomes: list[JudgeOutcome] = []
    for metric in RAG_JUDGE_METRICS:
        if metric not in requested:
            continue

        reason = _skip_reason(metric, trace=trace, contexts=contexts, gold_answer=gold_answer)
        if reason is not None:
            outcomes.append(
                _skipped(
                    metric,
                    reason,
                    prompt_version=resolved_prompt_version,
                )
            )
            continue

        agent = factory(metric)
        agent_schema_version = getattr(agent, "schema_version", resolved_schema_version)
        started = time.perf_counter()
        result = await agent.judge(
            _payload(metric, trace=trace, contexts=contexts, gold_answer=gold_answer),
            session=session,
            scope=f"rag_judge:{trace.id}:{metric}",
            user_id=trace.user_id,
            task_id=trace.task_id,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_output, raw_truncated = _truncate_raw(result.raw_text)
        config = _judge_config(agent, model=str(result.metadata.get("model") or "") or None)

        if not result.success or result.data is None:
            outcomes.append(
                JudgeOutcome(
                    metric_name=metric,
                    metric_version=agent.metric_version,
                    status="failed",
                    details={"errors": list(result.errors), **_usage_details(result)},
                    judge_config=config,
                    raw_output=raw_output,
                    raw_truncated=raw_truncated,
                    latency_ms=latency_ms,
                    error_message=("; ".join(result.errors) or "judge failed")[:2000],
                )
            )
            logger.warning(
                "rag judge failed trace={} metric={} error={}",
                trace.id,
                metric,
                result.errors[:1],
            )
            continue

        data = dict(result.data)
        if metric == "faithfulness":
            score, details, skipped_reason = _faithfulness_score(
                data,
                contexts=contexts,
                schema_version=agent_schema_version,
            )
            if skipped_reason is not None:
                outcomes.append(
                    JudgeOutcome(
                        metric_name=metric,
                        metric_version=agent.metric_version,
                        status="skipped",
                        skipped_reason=skipped_reason,
                        details={**details, **_usage_details(result)},
                        judge_config=config,
                        raw_output=raw_output,
                        raw_truncated=raw_truncated,
                        latency_ms=latency_ms,
                    )
                )
                continue
            outcomes.append(
                JudgeOutcome(
                    metric_name=metric,
                    metric_version=agent.metric_version,
                    status="evaluated",
                    score=score,
                    details={**details, **_usage_details(result)},
                    judge_config=config,
                    raw_output=raw_output,
                    raw_truncated=raw_truncated,
                    latency_ms=latency_ms,
                )
            )
            continue

        score_value = data.get("score")
        score = float(score_value) if isinstance(score_value, (int, float)) else None
        if score is None or not math.isfinite(score) or score < 0 or score > 1:
            outcomes.append(
                JudgeOutcome(
                    metric_name=metric,
                    metric_version=agent.metric_version,
                    status="failed",
                    details={"invalid_score": score_value, **_usage_details(result)},
                    judge_config=config,
                    raw_output=raw_output,
                    raw_truncated=raw_truncated,
                    latency_ms=latency_ms,
                    error_message="invalid score (must be finite and within [0, 1])",
                )
            )
            continue

        outcomes.append(
            JudgeOutcome(
                metric_name=metric,
                metric_version=agent.metric_version,
                status="evaluated",
                score=round(score, 6),
                details={
                    key: value
                    for key, value in data.items()
                    if key in ("reason", "missing_points", "wrong_facts")
                }
                | _usage_details(result),
                judge_config=config,
                raw_output=raw_output,
                raw_truncated=raw_truncated,
                latency_ms=latency_ms,
            )
        )

    return outcomes


__all__ = [
    "AgentFactory",
    "JudgeOutcome",
    "JudgeStatus",
    "MAX_CONTEXTS",
    "MAX_CONTEXT_CHARS",
    "MAX_RAW_CHARS",
    "judge_trace",
]
