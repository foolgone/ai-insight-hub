"""B-202 Prometheus 指标测试。"""
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
    calls = _value("llm_calls_total", {"model": model, "status": "success"})
    tokens_in = _value("llm_tokens_total", {"model": model, "direction": "input"})
    tokens_out = _value("llm_tokens_total", {"model": model, "direction": "output"})
    cost = _value("llm_cost_usd_total", {"model": model})
    latency_count = _value("llm_latency_seconds_count", {"model": model})

    metrics.record_llm_call(
        model=model,
        status="success",
        duration_seconds=0.42,
        input_tokens=11,
        output_tokens=7,
        cost_usd=0.002,
    )

    assert _value("llm_calls_total", {"model": model, "status": "success"}) == calls + 1
    assert _value("llm_tokens_total", {"model": model, "direction": "input"}) == tokens_in + 11
    assert _value("llm_tokens_total", {"model": model, "direction": "output"}) == tokens_out + 7
    assert _value("llm_cost_usd_total", {"model": model}) == pytest.approx(cost + 0.002)
    assert _value("llm_latency_seconds_count", {"model": model}) == latency_count + 1


def test_record_failed_llm_call() -> None:
    model = "m-failed-test"
    metrics.record_llm_call(model=model, status="failed", duration_seconds=0.1)

    assert _value("llm_calls_total", {"model": model, "status": "failed"}) == 1
    assert _value("llm_tokens_total", {"model": model, "direction": "input"}) == 0
    assert _value("llm_cost_usd_total", {"model": model}) == 0


def test_record_agent_invocation() -> None:
    agent = "cleaning-agent-test"
    metrics.record_agent_invocation(agent=agent, status="success", duration_seconds=1.2)

    assert _value("agent_invocations_total", {"agent": agent, "status": "success"}) == 1
    assert _value("agent_duration_seconds_count", {"agent": agent}) == 1


def test_metrics_endpoint_exposes_llm_metrics(client) -> None:
    metrics.record_llm_call(
        model="m-endpoint-test",
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
