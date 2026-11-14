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

from app.agents.rag_judge_agent import RagJudgeAgent
from app.models import QaDatasetItem, RagTrace
from app.schemas.agents.rag_judge import (
    RAG_JUDGE_METRICS,
    RAG_JUDGE_METRIC_VERSION,
    RagJudgeMetric,
)

JudgeStatus = Literal["evaluated", "skipped", "failed"]

# 上下文与原始输出上限：避免把超长 Trace 原样塞进 Prompt / 结果
MAX_CONTEXTS = 20
MAX_CONTEXT_CHARS = 6000
MAX_RAW_CHARS = 20000

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
        "prompt_version": agent.config.version,
        "prompt_sha256": agent.prompt_sha256,
        "metric_version": agent.metric_version,
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


def _skipped(metric: RagJudgeMetric, reason: str, *, model: str | None = None) -> JudgeOutcome:
    return JudgeOutcome(
        metric_name=metric,
        metric_version=RAG_JUDGE_METRIC_VERSION[metric],
        status="skipped",
        skipped_reason=reason,
        judge_config={
            "agent": f"rag_judge_{metric}",
            "model": model,
            "metric_version": RAG_JUDGE_METRIC_VERSION[metric],
        },
    )


def _faithfulness_score(data: dict[str, Any]) -> tuple[float | None, dict[str, Any], str | None]:
    """返回 ``(score, details, skipped_reason)``；无 claims 时 score=None。"""
    claims = list(data.get("claims") or [])
    total = len(claims)
    if total == 0:
        return None, {"claims": [], "reason": data.get("reason") or ""}, "no_claims"
    supported = sum(1 for claim in claims if claim.get("supported"))
    return (
        round(supported / total, 6),
        {
            "claims": claims,
            "supported_count": supported,
            "claim_count": total,
            "reason": data.get("reason") or "",
        },
        None,
    )


async def judge_trace(
    session: AsyncSession | None,
    *,
    trace: RagTrace,
    item: QaDatasetItem | None = None,
    metrics: Sequence[RagJudgeMetric] | None = None,
    agent_factory: AgentFactory | None = None,
) -> list[JudgeOutcome]:
    """对一条 Trace 执行指定指标；返回按 ``RAG_JUDGE_METRICS`` 顺序排列的结果。"""
    requested = list(metrics or RAG_JUDGE_METRICS)
    unknown = [metric for metric in requested if metric not in RAG_JUDGE_METRICS]
    if unknown:
        raise ValueError(f"unknown rag judge metrics: {unknown}")

    contexts = _contexts_from_trace(trace)
    gold_answer = _gold_answer_of(item)
    factory: AgentFactory = agent_factory or (lambda metric: RagJudgeAgent(metric))

    outcomes: list[JudgeOutcome] = []
    for metric in RAG_JUDGE_METRICS:
        if metric not in requested:
            continue

        reason = _skip_reason(metric, trace=trace, contexts=contexts, gold_answer=gold_answer)
        if reason is not None:
            outcomes.append(_skipped(metric, reason))
            continue

        agent = factory(metric)
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
                    details={"errors": list(result.errors)},
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
            score, details, skipped_reason = _faithfulness_score(data)
            if skipped_reason is not None:
                outcomes.append(
                    JudgeOutcome(
                        metric_name=metric,
                        metric_version=agent.metric_version,
                        status="skipped",
                        skipped_reason=skipped_reason,
                        details=details,
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
                    details=details,
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
                    details={"invalid_score": score_value},
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
                },
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
