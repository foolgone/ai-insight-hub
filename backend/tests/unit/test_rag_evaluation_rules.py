"""RAG 批量评测规则单测（Phase 3C）：指标版本、聚合口径、状态边界辅助。

不依赖数据库；DB 状态机由集成测试覆盖。
"""
from __future__ import annotations

import uuid

import pytest

from app.models import RagEvaluationResult, RagEvaluationRun
from app.schemas.rag_evaluation import RagEvaluationCreate
from app.services.rag_evaluation_service import (
    build_aggregate,
    expected_metrics,
    metric_version_for,
)

pytestmark = pytest.mark.unit


def _run(**overrides) -> RagEvaluationRun:
    values = {
        "id": uuid.uuid4(),
        "dataset_name": "doc-ds",
        "dataset_version_id": uuid.uuid4(),
        "execution_mode": "retrieve",
        "adapter": "mock",
        "retrieval_config": {"top_k": 5, "precision_mode": "at_k"},
        "config_snapshot": {
            "metrics": ["hit_rate", "context_recall", "context_precision_at_k"],
            "judge_metrics": [],
            "dataset_source_type": "doc",
        },
        "total_items": 2,
        "completed_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
    }
    values.update(overrides)
    return RagEvaluationRun(**values)


def _row(
    metric: str, status: str, score: float | None, reason: str | None = None
) -> RagEvaluationResult:
    return RagEvaluationResult(
        run_id=uuid.uuid4(),
        dataset_item_id=uuid.uuid4(),
        metric_name=metric,
        metric_version="v1",
        status=status,
        score=score,
        skipped_reason=reason,
        details={},
    )


def test_metric_version_mapping() -> None:
    assert metric_version_for("hit_rate") == "v1"
    assert metric_version_for("faithfulness") == "v1"


def test_expected_metrics_merges_retrieval_and_judge() -> None:
    run = _run(
        config_snapshot={
            "metrics": ["hit_rate"],
            "judge_metrics": ["faithfulness", "answer_relevancy"],
        }
    )

    assert expected_metrics(run) == ["hit_rate", "faithfulness", "answer_relevancy"]


def test_aggregate_skipped_and_failed_are_not_zero() -> None:
    run = _run(total_items=2)
    rows = [
        _row("hit_rate", "evaluated", 1.0),
        _row("hit_rate", "evaluated", 0.0),
        _row("hit_rate", "skipped", None, "gold_evidence_missing"),
        _row("context_recall", "skipped", None, "gold_evidence_missing"),
        _row("context_recall", "failed", None),
    ]

    aggregate = build_aggregate(run, rows, unprocessed_items=0)

    hit = aggregate["metrics"]["hit_rate"]
    assert hit["mean"] == pytest.approx(0.5)
    assert hit["evaluated"] == 2
    assert hit["skipped"] == 1
    assert hit["failed"] == 0
    assert hit["coverage"] == pytest.approx(1.0)
    assert hit["skip_reasons"] == {"gold_evidence_missing": 1}

    recall = aggregate["metrics"]["context_recall"]
    assert recall["mean"] is None  # 无 evaluated → None，不是 0
    assert recall["skipped"] == 1
    assert recall["failed"] == 1
    assert recall["coverage"] == 0.0


def test_aggregate_keeps_metric_version() -> None:
    run = _run(total_items=1)
    aggregate = build_aggregate(run, [_row("hit_rate", "evaluated", 0.5)], unprocessed_items=0)

    assert aggregate["metrics"]["hit_rate"]["metric_version"] == "v1"


# --------------------------------------------------------------------------- Schema 校验


def test_retrieve_mode_defaults_and_precision_variant() -> None:
    payload = RagEvaluationCreate(
        dataset_version_id=uuid.uuid4(),
        execution_mode="retrieve",
        precision_mode="ap",
    )

    assert payload.metrics == [
        "hit_rate",
        "mrr",
        "context_recall",
        "context_precision_ap_at_k",
    ]
    assert payload.judge_metrics is None


def test_retrieve_rejects_judge_metrics() -> None:
    with pytest.raises(ValueError):
        RagEvaluationCreate(
            dataset_version_id=uuid.uuid4(),
            execution_mode="retrieve",
            judge_metrics=["faithfulness"],
        )


def test_retrieve_rejects_two_precision_variants() -> None:
    with pytest.raises(ValueError):
        RagEvaluationCreate(
            dataset_version_id=uuid.uuid4(),
            execution_mode="retrieve",
            metrics=["hit_rate", "context_precision_at_k", "context_precision_ap_at_k"],
        )


def test_query_mode_rejects_retrieval_metrics() -> None:
    with pytest.raises(ValueError):
        RagEvaluationCreate(
            dataset_version_id=uuid.uuid4(),
            execution_mode="query",
            metrics=["hit_rate"],
        )


def test_query_mode_defaults_to_all_judge_metrics() -> None:
    payload = RagEvaluationCreate(dataset_version_id=uuid.uuid4(), execution_mode="query")

    assert payload.judge_metrics == [
        "faithfulness",
        "answer_correctness",
        "answer_relevancy",
    ]
