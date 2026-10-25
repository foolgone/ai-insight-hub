"""B-202 / B-608 Prometheus 指标测试（label 与可观测文档一致）。"""
from __future__ import annotations

import pytest
from prometheus_client import REGISTRY

from app.core import metrics

pytestmark = pytest.mark.unit


def _value(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return 0.0 if value is None else value


def test_record_llm_call_updates_all_metrics() -> None:
    model = "m-metrics-test"
    agent = "cleaning_agent"
    labels = {"model": model, "agent_name": agent}
    calls = _value("llm_calls_total", {**labels, "status": "success"})
    tokens_in = _value("llm_tokens_total", {**labels, "direction": "input"})
    tokens_out = _value("llm_tokens_total", {**labels, "direction": "output"})
    cost = _value("llm_cost_usd_total", labels)
    latency_count = _value("llm_latency_seconds_count", labels)

    metrics.record_llm_call(
        model=model,
        agent_name=agent,
        status="success",
        duration_seconds=0.42,
        input_tokens=11,
        output_tokens=7,
        cost_usd=0.002,
    )

    assert _value("llm_calls_total", {**labels, "status": "success"}) == calls + 1
    assert _value("llm_tokens_total", {**labels, "direction": "input"}) == tokens_in + 11
    assert _value("llm_tokens_total", {**labels, "direction": "output"}) == tokens_out + 7
    assert _value("llm_cost_usd_total", labels) == pytest.approx(cost + 0.002)
    assert _value("llm_latency_seconds_count", labels) == latency_count + 1


def test_record_failed_llm_call() -> None:
    model = "m-failed-test"
    agent = "evaluation_agent"
    labels = {"model": model, "agent_name": agent}
    metrics.record_llm_call(
        model=model,
        agent_name=agent,
        status="failed",
        duration_seconds=0.1,
    )

    assert _value("llm_calls_total", {**labels, "status": "failed"}) == 1
    assert _value("llm_tokens_total", {**labels, "direction": "input"}) == 0
    assert _value("llm_cost_usd_total", labels) == 0


def test_record_agent_invocation() -> None:
    agent = "cleaning-agent-test"
    metrics.record_agent_invocation(agent=agent, status="success", duration_seconds=1.2)

    assert _value("agent_invocations_total", {"agent": agent, "status": "success"}) == 1
    assert _value("agent_duration_seconds_count", {"agent": agent}) == 1


def test_metrics_endpoint_exposes_llm_metrics(client) -> None:
    metrics.record_llm_call(
        model="m-endpoint-test",
        agent_name="insight_agent",
        status="success",
        duration_seconds=0.2,
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.001,
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    for metric_name in (
        "llm_calls_total",
        "llm_tokens_total",
        "llm_cost_usd_total",
        "llm_latency_seconds",
        "agent_invocations_total",
    ):
        assert metric_name in body
