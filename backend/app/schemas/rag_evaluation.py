"""RAG 批量评测 Schemas（Phase 3C）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

ExecutionMode = Literal["retrieve", "query"]
PrecisionMode = Literal["at_k", "ap"]
RetryScope = Literal["all", "failed_only"]

RETRIEVAL_METRICS: tuple[str, ...] = (
    "hit_rate",
    "mrr",
    "context_recall",
    "context_precision_at_k",
    "context_precision_ap_at_k",
)
JUDGE_METRICS: tuple[str, ...] = (
    "faithfulness",
    "answer_correctness",
    "answer_relevancy",
)
DEFAULT_RETRIEVAL_METRICS: tuple[str, ...] = (
    "hit_rate",
    "mrr",
    "context_recall",
    "context_precision_at_k",
)
MAX_ITEMS = 200


class RagEvaluationCreate(BaseSchema):
    dataset_version_id: uuid.UUID
    execution_mode: ExecutionMode
    adapter: str = Field(default="mock", max_length=50)
    split: Literal["train", "valid", "test"] = "test"
    limit: int = Field(default=MAX_ITEMS, ge=1, le=MAX_ITEMS)
    top_k: int = Field(default=5, ge=1, le=50)
    precision_mode: PrecisionMode = "at_k"
    metrics: list[str] | None = None
    judge_metrics: list[str] | None = None
    item_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def _validate_metrics(self) -> RagEvaluationCreate:
        if self.execution_mode == "retrieve":
            if self.judge_metrics:
                raise ValueError("retrieve 模式不能包含 judge_metrics")
            chosen = list(self.metrics or DEFAULT_RETRIEVAL_METRICS)
            unknown = [item for item in chosen if item not in RETRIEVAL_METRICS]
            if unknown:
                raise ValueError(f"未知检索指标: {unknown}")
            if "context_precision_at_k" in chosen and "context_precision_ap_at_k" in chosen:
                raise ValueError("context_precision_at_k 与 context_precision_ap_at_k 只能选一个")
            expected_precision = (
                "context_precision_ap_at_k"
                if self.precision_mode == "ap"
                else "context_precision_at_k"
            )
            chosen = [item for item in chosen if not item.startswith("context_precision")]
            chosen.append(expected_precision)
            self.metrics = chosen
            return self

        if self.metrics:
            raise ValueError("query 模式不能包含检索指标")
        chosen_judge = list(self.judge_metrics or JUDGE_METRICS)
        unknown_judge = [item for item in chosen_judge if item not in JUDGE_METRICS]
        if unknown_judge:
            raise ValueError(f"未知 Judge 指标: {unknown_judge}")
        self.judge_metrics = chosen_judge
        return self


class RagEvaluationCreated(BaseSchema):
    run_id: uuid.UUID
    task_id: uuid.UUID
    status: str


class RagEvaluationResultRead(BaseSchema):
    id: uuid.UUID
    run_id: uuid.UUID
    dataset_item_id: uuid.UUID
    trace_id: uuid.UUID | None
    metric_name: str
    metric_version: str
    status: str
    score: float | None
    skipped_reason: str | None
    details: dict[str, Any]
    judge_config: dict[str, Any]
    raw_output: str | None
    raw_truncated: bool
    latency_ms: int | None
    error_message: str | None
    created_at: datetime


class RagEvaluationRunRead(BaseSchema):
    id: uuid.UUID
    task_id: uuid.UUID | None
    task_status: str | None = None
    task_progress: int | None = None
    parent_run_id: uuid.UUID | None
    attempt: int
    retry_scope: str
    dataset_id: uuid.UUID | None
    dataset_name: str
    dataset_version_id: uuid.UUID
    dataset_checksum: str | None
    execution_mode: str
    adapter: str
    retrieval_config: dict[str, Any]
    judge_config: dict[str, Any]
    config_snapshot: dict[str, Any]
    item_selection: dict[str, Any]
    total_items: int
    completed_items: int
    skipped_items: int
    failed_items: int
    status: str
    aggregate: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RagEvaluationRunListItem(BaseSchema):
    id: uuid.UUID
    task_id: uuid.UUID | None
    task_status: str | None = None
    parent_run_id: uuid.UUID | None
    attempt: int
    dataset_name: str
    dataset_version_id: uuid.UUID
    execution_mode: str
    adapter: str
    total_items: int
    completed_items: int
    skipped_items: int
    failed_items: int
    status: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class MetricAggregate(BaseSchema):
    metric_name: str
    metric_version: str
    mean: float | None
    evaluated: int
    skipped: int
    failed: int
    coverage: float
    skip_reasons: dict[str, int] = Field(default_factory=dict)


class EvaluationSummaryGroup(BaseSchema):
    dataset_id: uuid.UUID | None
    dataset_name: str
    source_type: str
    execution_mode: str
    adapter: str
    run_count: int
    total_items: int
    metrics: list[MetricAggregate]


class RagEvaluationSummary(BaseSchema):
    groups: list[EvaluationSummaryGroup]


__all__ = [
    "DEFAULT_RETRIEVAL_METRICS",
    "JUDGE_METRICS",
    "MAX_ITEMS",
    "RETRIEVAL_METRICS",
    "EvaluationSummaryGroup",
    "RagEvaluationCreated",
    "MetricAggregate",
    "RagEvaluationCreate",
    "RagEvaluationResultRead",
    "RagEvaluationRunListItem",
    "RagEvaluationRunRead",
    "RagEvaluationSummary",
]
