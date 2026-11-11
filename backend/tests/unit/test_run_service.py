"""批次对比纯函数单测（``app.services.run_service.build_comparison``）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.models import AnalysisResult, Task
from app.services.run_service import MIN_REPORTED_DELTA, build_comparison

_COMPLETED = datetime(2026, 11, 1, 10, 0, 0)


def _task(*, status: str = "completed", evaluated: int = 2) -> Task:
    return Task(
        id=uuid.uuid4(),
        task_type="evaluate",
        status=status,
        result={"evaluated": evaluated, "total": evaluated},
        completed_at=_COMPLETED,
    )


def _row(
    data_id: uuid.UUID,
    score: float,
    *,
    dimensions: dict | None = None,
    needs_review: bool = False,
) -> AnalysisResult:
    return AnalysisResult(
        id=uuid.uuid4(),
        datasource_id=uuid.uuid4(),
        data_id=data_id,
        task_id=uuid.uuid4(),
        analysis_type="quality",
        result={
            "overall_score": score,
            "dimensions": dimensions or {},
            "needs_review": needs_review,
        },
        agent_name="evaluation_agent",
    )


def test_compare_reports_average_dimension_and_band_deltas() -> None:
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    base = _task()
    target = _task()
    base_rows = [
        _row(d1, 80.0, dimensions={"accuracy": {"score": 80}, "tone": {"score": 90}}),
        _row(d2, 60.0, dimensions={"accuracy": {"score": 60}, "tone": {"score": 70}}),
    ]
    # d1 提升 10 分（进入 good），d2 提升 15 分（仍 fair）；accuracy 均分 +12.5
    target_rows = [
        _row(d1, 90.0, dimensions={"accuracy": {"score": 92}, "tone": {"score": 90}}),
        _row(d2, 75.0, dimensions={"accuracy": {"score": 73}, "tone": {"score": 70}}),
    ]

    result = build_comparison(base, base_rows, target, target_rows)

    assert result.base.avg_overall_score == 70.0
    assert result.target.avg_overall_score == 82.5
    assert result.delta.avg_overall_score == 12.5
    assert result.delta.sample_count == 0

    by_name = {item.name: item for item in result.dimensions}
    assert by_name["accuracy"].delta == 12.5
    assert by_name["tone"].delta == 0.0

    # 80→90 由 good 进入 excellent；60→75 由 fair 进入 good
    assert result.delta.bands.excellent == 1
    assert result.delta.bands.good == 0
    assert result.delta.bands.fair == -1


def test_compare_surfaces_regressions_and_improvements_per_dialogue() -> None:
    d_regressed, d_improved, d_flat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    base = _task()
    target = _task()
    base_rows = [_row(d_regressed, 90.0), _row(d_improved, 60.0), _row(d_flat, 80.0)]
    target_rows = [_row(d_regressed, 70.0), _row(d_improved, 85.0), _row(d_flat, 80.5)]

    result = build_comparison(base, base_rows, target, target_rows)

    assert [item.data_id for item in result.regressions] == [d_regressed]
    assert result.regressions[0].delta == -20.0
    assert [item.data_id for item in result.improvements] == [d_improved]
    # 0.5 分属于噪声（< MIN_REPORTED_DELTA），不应出现在任一列表
    assert result.improvements[0].delta >= MIN_REPORTED_DELTA
    assert all(item.data_id != d_flat for item in result.regressions + result.improvements)


def test_compare_counts_added_and_removed_dialogues() -> None:
    shared, only_base, only_target = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    base = _task()
    target = _task()
    base_rows = [_row(shared, 70.0), _row(only_base, 60.0)]
    target_rows = [_row(shared, 72.0), _row(only_target, 88.0)]

    result = build_comparison(base, base_rows, target, target_rows)

    assert result.added_items == 1
    assert result.removed_items == 1
    # 平均分变化会被样本差异放大/掩盖，因此单独暴露条数，避免误读
    assert result.base.sample_count == 2
    assert result.target.sample_count == 2


def test_compare_issue_diff_normalizes_whitespace_and_case() -> None:
    d = uuid.uuid4()
    base = _task()
    target = _task()
    base_rows = [
        _row(
            d,
            70.0,
            dimensions={
                "accuracy": {"score": 70, "issues": ["未回答 运费 问题", "语气生硬"]},
                "hallucination": {"score": 60, "issues": ["编造 优惠 活动"]},
            },
        )
    ]
    target_rows = [
        _row(
            d,
            72.0,
            dimensions={
                # 同一问题换个空格/大小写 → 视为仍然存在，不算「新增」
                "accuracy": {"score": 72, "issues": ["未回答运费问题"]},
                "hallucination": {"score": 64, "issues": ["编造优惠活动", "价格 说错"]},
            },
        )
    ]

    result = build_comparison(base, base_rows, target, target_rows)

    assert any("价格" in item for item in result.issues_added)
    assert any("语气生硬" in item for item in result.issues_removed)
    # 归一化后仍存在的问题不应出现在新增/消失里
    assert not any("未回答" in item for item in result.issues_added)
    assert not any("编造" in item for item in result.issues_removed)


def test_compare_with_empty_batches_does_not_crash() -> None:
    base = _task(evaluated=0)
    target = _task(evaluated=0)

    result = build_comparison(base, [], target, [])

    assert result.base.avg_overall_score == 0.0
    assert result.target.avg_overall_score == 0.0
    assert result.delta.avg_overall_score == 0.0
    assert result.dimensions == []
    assert result.regressions == []
    assert result.added_items == 0
