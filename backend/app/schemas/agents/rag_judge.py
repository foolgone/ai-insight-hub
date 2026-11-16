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

# v1.1.1 起 Faithfulness 分母/字段语义变化，指标版本升 v2；v1/v2 不混算。
JUDGE_SCHEMA_V1 = "rag_judge_schema_v1"
JUDGE_SCHEMA_V2 = "rag_judge_schema_v2"
JUDGE_V2_PROMPT_VERSIONS: frozenset[str] = frozenset({"v1.1.1"})

RAG_JUDGE_METRIC_VERSION_V2: dict[str, str] = {
    "faithfulness": "v2",
    "answer_correctness": "v2",
    "answer_relevancy": "v2",
}


def judge_schema_version(prompt_version: str | None) -> str:
    """Prompt 版本 → Schema 版本；未登记版本保持 v1 兼容行为。"""
    return JUDGE_SCHEMA_V2 if prompt_version in JUDGE_V2_PROMPT_VERSIONS else JUDGE_SCHEMA_V1


def metric_version_for_prompt(metric_name: str, prompt_version: str | None = None) -> str:
    """Judge 指标版本：v1.1.1 → v2；默认/其它 → v1。检索指标不在本函数内。"""
    if metric_name in RAG_JUDGE_METRICS and prompt_version in JUDGE_V2_PROMPT_VERSIONS:
        return RAG_JUDGE_METRIC_VERSION_V2[metric_name]
    return RAG_JUDGE_METRIC_VERSION.get(metric_name, "v1")


class EvidenceRef(BaseModel):
    """v1.1.1 逐字证据引用：C1..Cn + 原文片段。"""

    context_id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=2000)


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
    """v1/v2 兼容的 claim。

    v1.0.0：``supported`` + ``evidence`` 为事实源；
    v1.1.1：``support_status`` + ``evidence_refs`` 为事实源，旧字段保留可解析。
    """

    claim: str = Field(min_length=1, max_length=2000)
    supported: bool | None = None
    evidence: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(default="", max_length=1000)
    claim_id: str | None = Field(default=None, max_length=32)
    claim_type: Literal["factual_claim", "non_factual"] = "factual_claim"
    claim_subtype: Literal["policy", "absence", "conflict", "advice", "meta"] | None = None
    support_status: Literal["supported", "unsupported", "insufficient_evidence"] | None = None
    is_contradictory: bool = False
    contradiction_with: list[str] = Field(default_factory=list, max_length=20)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=20)


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
    "EvidenceRef",
    "FaithfulnessClaim",
    "FaithfulnessOutput",
    "JUDGE_SCHEMA_V1",
    "JUDGE_SCHEMA_V2",
    "JUDGE_V2_PROMPT_VERSIONS",
    "METRIC_OUTPUT_SCHEMAS",
    "RAG_JUDGE_METRICS",
    "RAG_JUDGE_METRIC_VERSION",
    "RAG_JUDGE_METRIC_VERSION_V2",
    "RagJudgeInput",
    "RagJudgeMetric",
    "judge_schema_version",
    "metric_version_for_prompt",
]
