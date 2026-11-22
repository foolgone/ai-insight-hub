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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RagJudgeMetric = Literal["faithfulness", "answer_correctness", "answer_relevancy"]

RAG_JUDGE_METRICS: tuple[RagJudgeMetric, ...] = (
    "faithfulness",
    "answer_correctness",
    "answer_relevancy",
)

FAITHFULNESS_STRICT_METRIC = "faithfulness_strict"
RAG_JUDGE_DERIVED_METRICS: tuple[str, ...] = (FAITHFULNESS_STRICT_METRIC,)

# 指标版本：与 Prompt 版本解耦（Prompt 可迭代，指标口径不变则版本不变）
RAG_JUDGE_METRIC_VERSION: dict[str, str] = {
    "faithfulness": "v1",
    "answer_correctness": "v1",
    "answer_relevancy": "v1",
}

# v1.1.1 起 Faithfulness 分母/字段语义变化，指标版本升 v2；v1/v2 不混算。
JUDGE_SCHEMA_V1 = "rag_judge_schema_v1"
JUDGE_SCHEMA_V2 = "rag_judge_schema_v2"
JUDGE_SCHEMA_V3 = "rag_judge_schema_v3"
JUDGE_V2_PROMPT_VERSIONS: frozenset[str] = frozenset(
    {"v1.1.1", "v1.1.2", "v1.1.3", "v1.1.4", "v1.1.5"}
)
JUDGE_V3_PROMPT_VERSIONS: frozenset[str] = frozenset({"v1.2.0", "v1.2.1"})

RAG_JUDGE_METRIC_VERSION_V2: dict[str, str] = {
    "faithfulness": "v2",
    "answer_correctness": "v2",
    "answer_relevancy": "v2",
}

RAG_JUDGE_METRIC_VERSION_V3: dict[str, str] = {
    "faithfulness": "v3",
    "faithfulness_strict": "v3",
    "answer_correctness": "v3",
    "answer_relevancy": "v3",
}


def judge_schema_version(prompt_version: str | None) -> str:
    """Prompt 版本 → Schema 版本；未登记版本保持 v1 兼容行为。"""
    if prompt_version in JUDGE_V3_PROMPT_VERSIONS:
        return JUDGE_SCHEMA_V3
    return JUDGE_SCHEMA_V2 if prompt_version in JUDGE_V2_PROMPT_VERSIONS else JUDGE_SCHEMA_V1


def metric_version_for_prompt(metric_name: str, prompt_version: str | None = None) -> str:
    """Judge 指标版本：v1.2.0 → v3；v1.1.1 → v2；默认/其它 → v1。"""
    judge_metric = metric_name in RAG_JUDGE_METRICS or metric_name in RAG_JUDGE_DERIVED_METRICS
    if judge_metric:
        if prompt_version in JUDGE_V3_PROMPT_VERSIONS:
            return RAG_JUDGE_METRIC_VERSION_V3[metric_name]
        if prompt_version in JUDGE_V2_PROMPT_VERSIONS:
            return RAG_JUDGE_METRIC_VERSION_V2.get(metric_name, "v2")
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

    @field_validator("evidence", "contradiction_with", mode="before")
    @classmethod
    def _none_or_null_items_to_list(cls, value: object) -> object:
        """模型常把空数组写成 null；宽容化，避免仅因 null 触发修复轮。"""
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if item is not None]
        return value

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _none_or_null_refs_to_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if item is not None]
        return value

    @field_validator("is_contradictory", mode="before")
    @classmethod
    def _none_to_false(cls, value: object) -> object:
        return False if value is None else value

    @field_validator("claim_type", mode="before")
    @classmethod
    def _none_to_factual(cls, value: object) -> object:
        return "factual_claim" if value is None else value

    @field_validator("reason", mode="before")
    @classmethod
    def _none_to_empty_reason(cls, value: object) -> object:
        return "" if value is None else value


class FaithfulnessOutput(BaseModel):
    """Faithfulness 只输出 claims 与说明；总分由代码计算。"""

    claims: list[FaithfulnessClaim] = Field(default_factory=list, max_length=80)
    reason: str = Field(default="", max_length=1000)

    @field_validator("claims", mode="before")
    @classmethod
    def _none_claims_to_list(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("reason", mode="before")
    @classmethod
    def _none_reason_to_empty(cls, value: object) -> object:
        return "" if value is None else value


FACTUAL_CLAIM_SUBTYPES_V3: tuple[str, ...] = (
    "policy",
    "condition",
    "normative_requirement",
    "fact",
    "process",
    "derived",
    "policy_scope",
    "policy_relationship",
    "conflict",
)
NON_FACTUAL_CLAIM_SUBTYPES_V3: tuple[str, ...] = (
    "absence",
    "doc_scope",
    "doc_relationship",
    "uncertainty",
    "meta",
    "advice",
    "greeting",
)

FactualClaimSubtypeV3 = Literal[
    "policy",
    "condition",
    "normative_requirement",
    "fact",
    "process",
    "derived",
    "policy_scope",
    "policy_relationship",
    "conflict",
]
NonFactualClaimSubtypeV3 = Literal[
    "absence",
    "doc_scope",
    "doc_relationship",
    "uncertainty",
    "meta",
    "advice",
    "greeting",
]
ClaimSubtypeV3 = FactualClaimSubtypeV3 | NonFactualClaimSubtypeV3


class FaithfulnessClaimV3(BaseModel):
    """Schema v3 claim：显式 type/subtype/support_status/evidence_refs。"""

    model_config = ConfigDict(extra="forbid")

    claim_id: str | None = Field(default=None, max_length=32)
    claim: str = Field(min_length=1, max_length=2000)
    claim_type: Literal["factual_claim", "non_factual"]
    claim_subtype: ClaimSubtypeV3
    support_status: Literal["supported", "unsupported", "insufficient_evidence"] | None = None
    is_contradictory: bool = False
    contradiction_with: list[str] = Field(default_factory=list, max_length=20)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=20)
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _validate_v3_contract(self) -> FaithfulnessClaimV3:
        factual = self.claim_type == "factual_claim"
        if factual and self.claim_subtype in NON_FACTUAL_CLAIM_SUBTYPES_V3:
            raise ValueError(f"claim_subtype {self.claim_subtype!r} is not valid for factual_claim")
        if not factual and self.claim_subtype in FACTUAL_CLAIM_SUBTYPES_V3:
            raise ValueError(f"claim_subtype {self.claim_subtype!r} is not valid for non_factual")
        if factual and self.support_status is None:
            raise ValueError("factual_claim requires support_status")
        if not factual and self.support_status is not None:
            raise ValueError("non_factual must not have support_status")
        if factual and self.support_status == "supported" and not self.evidence_refs:
            raise ValueError("supported factual_claim requires evidence_refs")
        if factual and self.support_status == "insufficient_evidence" and self.evidence_refs:
            raise ValueError("insufficient_evidence must not have evidence_refs")
        if factual and self.claim_subtype == "conflict" and len(self.evidence_refs) < 2:
            raise ValueError("conflict claim requires at least two evidence_refs")
        return self

    @field_validator("contradiction_with", mode="before")
    @classmethod
    def _v3_none_or_null_items_to_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if item is not None]
        return value

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _v3_none_or_null_refs_to_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if item is not None]
        return value

    @field_validator("is_contradictory", mode="before")
    @classmethod
    def _v3_none_to_false(cls, value: object) -> object:
        return False if value is None else value

    @field_validator("reason", mode="before")
    @classmethod
    def _v3_none_to_empty_reason(cls, value: object) -> object:
        return "" if value is None else value


class FaithfulnessOutputV3(BaseModel):
    """Schema v3 faithfulness 输出：claims 使用严格 V3 claim。"""

    claims: list[FaithfulnessClaimV3] = Field(default_factory=list, max_length=80)
    reason: str = Field(default="", max_length=1000)

    @field_validator("claims", mode="before")
    @classmethod
    def _none_claims_to_list(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("reason", mode="before")
    @classmethod
    def _none_reason_to_empty(cls, value: object) -> object:
        return "" if value is None else value


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

METRIC_OUTPUT_SCHEMAS_V3: dict[str, type[BaseModel]] = {
    "faithfulness": FaithfulnessOutputV3,
    "answer_correctness": AnswerCorrectnessOutput,
    "answer_relevancy": AnswerRelevancyOutput,
}


def output_schema_for(metric: str, schema_version: str) -> type[BaseModel]:
    """按 Schema 版本选择输出模型；v3 只有 faithfulness 使用严格模型。"""
    if schema_version == JUDGE_SCHEMA_V3:
        return METRIC_OUTPUT_SCHEMAS_V3[metric]
    return METRIC_OUTPUT_SCHEMAS[metric]


__all__ = [
    "AnswerCorrectnessOutput",
    "AnswerRelevancyOutput",
    "ClaimSubtypeV3",
    "EvidenceRef",
    "FACTUAL_CLAIM_SUBTYPES_V3",
    "FAITHFULNESS_STRICT_METRIC",
    "FactualClaimSubtypeV3",
    "FaithfulnessClaim",
    "FaithfulnessClaimV3",
    "FaithfulnessOutput",
    "FaithfulnessOutputV3",
    "JUDGE_SCHEMA_V1",
    "JUDGE_SCHEMA_V2",
    "JUDGE_SCHEMA_V3",
    "JUDGE_V2_PROMPT_VERSIONS",
    "JUDGE_V3_PROMPT_VERSIONS",
    "METRIC_OUTPUT_SCHEMAS",
    "METRIC_OUTPUT_SCHEMAS_V3",
    "NON_FACTUAL_CLAIM_SUBTYPES_V3",
    "NonFactualClaimSubtypeV3",
    "RAG_JUDGE_DERIVED_METRICS",
    "RAG_JUDGE_METRICS",
    "RAG_JUDGE_METRIC_VERSION",
    "RAG_JUDGE_METRIC_VERSION_V2",
    "RAG_JUDGE_METRIC_VERSION_V3",
    "RagJudgeInput",
    "RagJudgeMetric",
    "judge_schema_version",
    "metric_version_for_prompt",
    "output_schema_for",
]
