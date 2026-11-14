"""RAG Judge 输入/输出 Schema（Phase 3B）。

三个指标严格隔离：
- ``faithfulness``：query + answer + contexts（只来自本次 Trace 的 agent 上下文）；
- ``answer_correctness``：query + answer + gold_answer；
- ``answer_relevancy``：query + answer。

输出 Schema 负责「结构合法」；业务合法性（如 score 越界）在 ``_validate_parsed`` /
服务层再次校验，避免模型自报异常分数被当成结果。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RagJudgeMetric = Literal["faithfulness", "answer_correctness", "answer_relevancy"]

RAG_JUDGE_METRICS: tuple[RagJudgeMetric, ...] = (
    "faithfulness",
    "answer_correctness",
    "answer_relevancy",
)

# 指标版本：与 Prompt 版本解耦（Prompt 可迭代，指标口径不变则版本不变）
RAG_JUDGE_METRIC_VERSION: dict[str, str] = {
    "faithfulness": "v1",
    "answer_correctness": "v1",
    "answer_relevancy": "v1",
}


class RagJudgeInput(BaseModel):
    """统一输入（按 metric 在 Agent 里校验必填字段）。"""

    query: str = Field(min_length=1, max_length=5000)
    answer: str | None = Field(default=None, max_length=20000)
    contexts: list[str] = Field(default_factory=list, max_length=50)
    gold_answer: str | None = Field(default=None, max_length=20000)

    @field_validator("contexts")
    @classmethod
    def _strip_contexts(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class FaithfulnessClaim(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)
    supported: bool
    evidence: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(default="", max_length=1000)


class FaithfulnessOutput(BaseModel):
    """Faithfulness 只输出 claims 与说明；总分由代码计算。"""

    claims: list[FaithfulnessClaim] = Field(default_factory=list, max_length=80)
    reason: str = Field(default="", max_length=1000)


class AnswerCorrectnessOutput(BaseModel):
    score: float = Field(ge=0, le=1)
    missing_points: list[str] = Field(default_factory=list, max_length=30)
    wrong_facts: list[str] = Field(default_factory=list, max_length=30)
    reason: str = Field(default="", max_length=1000)


class AnswerRelevancyOutput(BaseModel):
    score: float = Field(ge=0, le=1)
    reason: str = Field(default="", max_length=1000)


METRIC_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "faithfulness": FaithfulnessOutput,
    "answer_correctness": AnswerCorrectnessOutput,
    "answer_relevancy": AnswerRelevancyOutput,
}

__all__ = [
    "AnswerCorrectnessOutput",
    "AnswerRelevancyOutput",
    "FaithfulnessClaim",
    "FaithfulnessOutput",
    "METRIC_OUTPUT_SCHEMAS",
    "RAG_JUDGE_METRICS",
    "RAG_JUDGE_METRIC_VERSION",
    "RagJudgeInput",
    "RagJudgeMetric",
]
