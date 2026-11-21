"""RAG Judge 编排服务单测（Phase 3B）：跳过规则、隔离、版本元信息、截断。

全部使用 Stub Agent，不访问数据库 / 真实模型。
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.base import AgentResult
from app.models import QaDatasetItem, RagTrace
from app.services.rag_judge_service import MAX_RAW_CHARS, judge_trace

pytestmark = pytest.mark.unit


def _trace(**overrides: Any) -> RagTrace:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "adapter": "mock",
        "mode": "query",
        "context_source": "agent_chat",
        "query": "退款多久到账？",
        "answer": "退款 1-3 天到账。",
        "status": "success",
        "retrieved_contexts": [{"content": "退款将在 1-3 天内到账。"}],
    }
    values.update(overrides)
    return RagTrace(**values)


def _item(gold_answer: str | None = "退款 1-3 天到账。") -> QaDatasetItem:
    return QaDatasetItem(
        id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        item_key="Q001",
        query="退款多久到账？",
        gold_answer=gold_answer,
    )


class StubAgent:
    def __init__(
        self,
        metric: str,
        *,
        success: bool = True,
        data: dict[str, Any] | None = None,
        errors: list[str] | None = None,
        raw: str | None = "raw-output",
        prompt_version: str = "2026-11-14.1",
    ) -> None:
        self.metric = metric
        self.config = SimpleNamespace(
            name=f"rag_judge_{metric}",
            version=prompt_version,
            temperature=0.0,
            max_tokens=512,
        )
        self.metric_version = "v1"
        self.prompt_sha256 = "a" * 64
        self.calls = 0
        self.last_payload: dict[str, Any] | None = None
        self._result = AgentResult(
            success=success,
            data=data,
            errors=list(errors or []),
            metadata={"model": "stub-judge-model"},
            raw_text=raw,
        )

    async def judge(self, payload: dict[str, Any], **kwargs: Any) -> AgentResult:
        self.calls += 1
        self.last_payload = payload
        return self._result


def _factory(stubs: dict[str, StubAgent]):
    def build(metric: str) -> StubAgent:
        return stubs[metric]

    return build


async def test_no_context_skips_without_calling_judge() -> None:
    trace = _trace(context_source="none", retrieved_contexts=[])
    called: list[str] = []

    def factory(metric: str) -> StubAgent:
        called.append(metric)
        return StubAgent(metric)

    outcomes = await judge_trace(None, trace=trace, metrics=["faithfulness"], agent_factory=factory)

    assert len(outcomes) == 1
    assert outcomes[0].status == "skipped"
    assert outcomes[0].skipped_reason == "context_unavailable"
    assert outcomes[0].score is None
    assert called == [], "无上下文时不得创建/调用 Judge"


async def test_retrieval_context_is_not_used_for_faithfulness() -> None:
    trace = _trace(context_source="hybrid_search")
    called: list[str] = []

    def factory(metric: str) -> StubAgent:
        called.append(metric)
        return StubAgent(metric)

    outcomes = await judge_trace(None, trace=trace, metrics=["faithfulness"], agent_factory=factory)

    assert outcomes[0].skipped_reason == "context_unavailable"
    assert called == []


async def test_no_claims_is_skipped_not_one() -> None:
    stub = StubAgent("faithfulness", data={"claims": [], "reason": ""})
    trace = _trace()

    outcomes = await judge_trace(
        None,
        trace=trace,
        metrics=["faithfulness"],
        agent_factory=_factory({"faithfulness": stub}),
    )

    assert outcomes[0].status == "skipped"
    assert outcomes[0].skipped_reason == "no_claims"
    assert outcomes[0].score is None


async def test_partial_support_computes_score_in_code() -> None:
    stub = StubAgent(
        "faithfulness",
        data={
            "claims": [
                {"claim": "a", "supported": True, "evidence": ["ctx"], "reason": ""},
                {"claim": "b", "supported": False, "evidence": [], "reason": "无依据"},
            ],
            "reason": "",
        },
    )

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["faithfulness"],
        agent_factory=_factory({"faithfulness": stub}),
    )

    assert outcomes[0].status == "evaluated"
    assert outcomes[0].score == pytest.approx(0.5)
    assert outcomes[0].details["supported_count"] == 1
    assert outcomes[0].details["claim_count"] == 2
    # Phase 3E：token/成本随结果带出（默认 StubAgent 未消耗）
    assert outcomes[0].details["token_usage"] == {"input": 0, "output": 0}
    assert outcomes[0].details["cost"] == "0"


async def test_correctness_requires_gold_answer() -> None:
    called: list[str] = []

    def factory(metric: str) -> StubAgent:
        called.append(metric)
        return StubAgent(metric)

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        item=_item(gold_answer=None),
        metrics=["answer_correctness"],
        agent_factory=factory,
    )

    assert outcomes[0].skipped_reason == "gold_answer_missing"
    assert called == []


async def test_relevancy_requires_answer() -> None:
    outcomes = await judge_trace(
        None,
        trace=_trace(answer=""),
        metrics=["answer_relevancy"],
        agent_factory=_factory({"answer_relevancy": StubAgent("answer_relevancy")}),
    )

    assert outcomes[0].skipped_reason == "answer_missing"


async def test_failed_trace_skips_all_metrics() -> None:
    trace = _trace(status="failed")

    outcomes = await judge_trace(
        None,
        trace=trace,
        agent_factory=_factory({}),
    )

    assert [row.status for row in outcomes] == ["skipped"] * 3
    assert {row.skipped_reason for row in outcomes} == {"trace_failed"}


async def test_one_metric_failure_does_not_affect_others() -> None:
    stubs = {
        "faithfulness": StubAgent(
            "faithfulness",
            data={"claims": [{"claim": "a", "supported": True, "evidence": [], "reason": ""}]},
        ),
        "answer_correctness": StubAgent("answer_correctness", success=False, errors=["boom"]),
        "answer_relevancy": StubAgent("answer_relevancy", data={"score": 0.9, "reason": "ok"}),
    }

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        item=_item(),
        agent_factory=_factory(stubs),
    )

    by_metric = {row.metric_name: row for row in outcomes}
    assert by_metric["faithfulness"].status == "evaluated"
    assert by_metric["answer_correctness"].status == "failed"
    assert "boom" in (by_metric["answer_correctness"].error_message or "")
    assert by_metric["answer_relevancy"].status == "evaluated"
    assert by_metric["answer_relevancy"].score == pytest.approx(0.9)


async def test_raw_output_is_truncated_with_marker() -> None:
    stub = StubAgent("answer_relevancy", data={"score": 0.5}, raw="x" * (MAX_RAW_CHARS + 100))

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["answer_relevancy"],
        agent_factory=_factory({"answer_relevancy": stub}),
    )

    assert len(outcomes[0].raw_output or "") == MAX_RAW_CHARS
    assert outcomes[0].raw_truncated is True


async def test_judge_config_carries_versions_and_model() -> None:
    stub = StubAgent("answer_relevancy", data={"score": 0.5})

    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["answer_relevancy"],
        agent_factory=_factory({"answer_relevancy": stub}),
    )

    config = outcomes[0].judge_config
    assert config["model"] == "stub-judge-model"
    assert config["prompt_version"] == "2026-11-14.1"
    assert config["prompt_sha256"] == "a" * 64
    assert config["metric_version"] == "v1"


async def test_only_requested_metrics_are_returned() -> None:
    outcomes = await judge_trace(
        None,
        trace=_trace(),
        metrics=["answer_relevancy"],
        agent_factory=_factory(
            {"answer_relevancy": StubAgent("answer_relevancy", data={"score": 1.0})}
        ),
    )

    assert [row.metric_name for row in outcomes] == ["answer_relevancy"]


async def test_metric_inputs_are_isolated() -> None:
    stubs = {
        "faithfulness": StubAgent(
            "faithfulness",
            data={"claims": [{"claim": "a", "supported": True, "evidence": [], "reason": ""}]},
        ),
        "answer_correctness": StubAgent("answer_correctness", data={"score": 0.7}),
        "answer_relevancy": StubAgent("answer_relevancy", data={"score": 0.8}),
    }

    await judge_trace(None, trace=_trace(), item=_item(), agent_factory=_factory(stubs))

    faith_payload = stubs["faithfulness"].last_payload or {}
    assert "contexts" in faith_payload and "gold_answer" not in faith_payload

    correctness_payload = stubs["answer_correctness"].last_payload or {}
    assert "gold_answer" in correctness_payload and "contexts" not in correctness_payload

    relevancy_payload = stubs["answer_relevancy"].last_payload or {}
    assert "contexts" not in relevancy_payload and "gold_answer" not in relevancy_payload
