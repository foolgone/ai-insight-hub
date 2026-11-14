"""RAG Judge 集成测试（Phase 3B）：真实 DB 中的 Trace + Mock LLM。

验证：
- 三个指标可对一条已落库 Trace 执行；
- Judge 不修改 Trace（答案 / 上下文 / 状态保持不变）；
- 不同 Prompt 版本产生不同 judge_config（3C 据此保存多版本，不覆盖历史）。
"""
from __future__ import annotations


import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentConfig
from app.agents.rag_judge_agent import RagJudgeAgent
from app.core.llm import LLMResponse, LLMUsage
from app.models import QaDataset, QaDatasetItem, QaDatasetVersion, RagTrace
from app.services.rag_judge_service import judge_trace
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

FAITHFULNESS_JSON = (
    '{"claims": [{"claim": "退款 1-3 天到账", "supported": true,'
    ' "evidence": ["1-3 天内到账"], "reason": "上下文明确"}], "reason": "ok"}'
)
CORRECTNESS_JSON = '{"score": 0.9, "missing_points": [], "wrong_facts": [], "reason": "一致"}'
RELEVANCY_JSON = '{"score": 0.8, "reason": "直接回答"}'

RESPONSES = {
    "faithfulness": FAITHFULNESS_JSON,
    "answer_correctness": CORRECTNESS_JSON,
    "answer_relevancy": RELEVANCY_JSON,
}


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def chat(self, messages, **kwargs):  # noqa: ANN001, ANN002
        self.calls += 1
        return LLMResponse(
            content=self.content,
            usage=LLMUsage(input_tokens=8, output_tokens=4),
            model="fake-judge-model",
            latency_ms=1.0,
        )

    async def aclose(self) -> None:
        return None


def _factory(prompt_version: str):
    def build(metric: str) -> RagJudgeAgent:
        return RagJudgeAgent(
            metric,  # type: ignore[arg-type]
            config=AgentConfig(
                name=f"rag_judge_{metric}",
                version=prompt_version,
                max_retries=0,
                timeout=5.0,
                max_tokens=512,
            ),
            llm=FakeLLM(RESPONSES[metric]),
        )

    return build


async def _seed(db_session: AsyncSession) -> tuple[RagTrace, QaDatasetItem]:
    user = UserFactory()
    await persist(db_session, user)

    dataset = QaDataset(user_id=user.id, name="judge-ds", source_type="doc")
    await persist(db_session, dataset)
    version = QaDatasetVersion(dataset_id=dataset.id, version=1, status="published", item_count=1)
    await persist(db_session, version)
    item = QaDatasetItem(
        version_id=version.id,
        item_key="Q001",
        query="退款多久到账？",
        gold_answer="退款 1-3 天到账。",
        gold_evidence=[],
        split="test",
    )
    await persist(db_session, item)

    trace = RagTrace(
        user_id=user.id,
        dataset_item_id=item.id,
        adapter="mock",
        mode="query",
        context_source="agent_chat",
        query="退款多久到账？",
        answer="退款 1-3 天到账。",
        retrieved_contexts=[{"content": "退款将在 1-3 天内到账。", "score": None}],
        status="success",
    )
    await persist(db_session, trace)
    return trace, item


async def test_judge_trace_end_to_end_with_mock_llm(db_session: AsyncSession) -> None:
    trace, item = await _seed(db_session)
    before = {
        "answer": trace.answer,
        "contexts": list(trace.retrieved_contexts),
        "status": trace.status,
    }

    outcomes = await judge_trace(
        db_session, trace=trace, item=item, agent_factory=_factory("2026-11-14.1")
    )

    by_metric = {row.metric_name: row for row in outcomes}
    assert len(outcomes) == 3
    assert by_metric["faithfulness"].status == "evaluated"
    assert by_metric["faithfulness"].score == pytest.approx(1.0)
    assert by_metric["answer_correctness"].score == pytest.approx(0.9)
    assert by_metric["answer_relevancy"].score == pytest.approx(0.8)
    assert all(row.judge_config["prompt_version"] == "2026-11-14.1" for row in outcomes)
    assert all(row.raw_output for row in outcomes)

    await db_session.refresh(trace)
    assert trace.answer == before["answer"]
    assert list(trace.retrieved_contexts) == before["contexts"]
    assert trace.status == before["status"]


async def test_different_prompt_versions_produce_different_config(db_session: AsyncSession) -> None:
    trace, item = await _seed(db_session)

    first = await judge_trace(
        db_session,
        trace=trace,
        item=item,
        metrics=["answer_relevancy"],
        agent_factory=_factory("v1.0"),
    )
    second = await judge_trace(
        db_session,
        trace=trace,
        item=item,
        metrics=["answer_relevancy"],
        agent_factory=_factory("v2.0"),
    )

    assert first[0].judge_config["prompt_version"] == "v1.0"
    assert second[0].judge_config["prompt_version"] == "v2.0"
    # 3B 不落库：两条结果互不覆盖，由 3C 按版本分别保存
    assert first[0].score == second[0].score
