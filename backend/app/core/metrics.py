"""Prometheus 指标（09-可观测与成本监控 §4；Agent 设计 §8.3）。

指标名是外部契约（Grafana/告警按名查询），**不得随意改名**：
- ``llm_calls_total{model,status}``
- ``llm_tokens_total{model,direction}``
- ``llm_cost_usd_total{model}``
- ``llm_latency_seconds{model}``
- ``agent_invocations_total{agent,status}``
- ``agent_duration_seconds{agent}``

成本对账只认 ``llm_calls`` 表，Prometheus 为进程内累加（不能用于月结）。
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

LLM_CALLS_TOTAL = Counter("llm_calls_total", "Total number of LLM calls", ["model", "status"])
LLM_TOKENS_TOTAL = Counter("llm_tokens_total", "Total number of LLM tokens", ["model", "direction"])
LLM_COST_USD_TOTAL = Counter("llm_cost_usd_total", "Cumulative LLM cost in USD", ["model"])
LLM_LATENCY_SECONDS = Histogram(
    "llm_latency_seconds",
    "LLM call latency in seconds",
    ["model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
AGENT_INVOCATIONS_TOTAL = Counter(
    "agent_invocations_total", "Total number of agent invocations", ["agent", "status"]
)
AGENT_DURATION_SECONDS = Histogram(
    "agent_duration_seconds",
    "Agent invocation duration in seconds",
    ["agent"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
)


def record_llm_call(
    *,
    model: str,
    status: str,
    duration_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """记录一次 LLM 调用（成功或失败）。"""
    LLM_CALLS_TOTAL.labels(model=model, status=status).inc()
    if input_tokens:
        LLM_TOKENS_TOTAL.labels(model=model, direction="input").inc(input_tokens)
    if output_tokens:
        LLM_TOKENS_TOTAL.labels(model=model, direction="output").inc(output_tokens)
    if cost_usd:
        LLM_COST_USD_TOTAL.labels(model=model).inc(cost_usd)
    LLM_LATENCY_SECONDS.labels(model=model).observe(duration_seconds)


def record_agent_invocation(*, agent: str, status: str, duration_seconds: float) -> None:
    """记录一次 Agent 执行（成功/失败/降级）。"""
    AGENT_INVOCATIONS_TOTAL.labels(agent=agent, status=status).inc()
    AGENT_DURATION_SECONDS.labels(agent=agent).observe(duration_seconds)


__all__ = [
    "AGENT_DURATION_SECONDS",
    "AGENT_INVOCATIONS_TOTAL",
    "LLM_CALLS_TOTAL",
    "LLM_COST_USD_TOTAL",
    "LLM_LATENCY_SECONDS",
    "LLM_TOKENS_TOTAL",
    "record_agent_invocation",
    "record_llm_call",
]
