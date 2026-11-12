"""批次（run）与批次对比。

一次评估任务 = 一个批次：同一次任务写出的 ``analysis_results`` 共享 ``task_id``。
本模块只做「列批次 + 比两批」，不改评估执行逻辑，用于回答：

    「同一批对话，改动前后质量到底变了没有？变在哪？」

设计取舍：
- **分数按对话对齐**（``data_id``），不是只比平均分——平均分相同也可能是一边涨一边跌；
- **问题文本只做归一化后求差集**：issues 是 LLM 自由文本，不具备稳定 ID，
  因此结果标注为「线索」，不做精确计数承诺；
- 历史数据没有 ``task_id``，不参与批次对比（宁可少一个批次，不伪造归属）。
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.evaluation_agent import quality_level_for
from app.core.errors import FrameworkErrorCode
from app.core.exceptions import AIInsightHubException, DataSourceNotFoundError
from app.core.ownership import assert_owner
from app.models import AnalysisResult, DataSource, Task, User
from app.repositories import analysis_results as analysis_repo
from app.schemas.agents.evaluation import ISSUE_CATEGORY_LABELS
from app.schemas.analysis import (
    DialogueDelta,
    DimensionDelta,
    InsightComparison,
    InsightMetric,
    IssueCategoryDelta,
    RunComparison,
    RunDelta,
    RunItem,
    RunOverview,
    ScoreBands,
)

EVALUATE_TASK_TYPE = "evaluate"
DEFAULT_RUN_LIMIT = 20
MAX_RUN_LIMIT = 50
DIMENSIONS: tuple[str, ...] = ("accuracy", "completeness", "hallucination", "tone", "compliance")
TOP_DELTAS = 5
MAX_ISSUES = 10
MIN_REPORTED_DELTA = 1.0  # 分差小于 1 分视为噪声，不进「改好/改坏」列表

_WHITESPACE = re.compile(r"\s+")


# --------------------------------------------------------------------------- 纯函数（可单测）


def _score_of(row: AnalysisResult) -> float:
    payload = row.result or {}
    try:
        return float(payload.get("overall_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _dimension_scores(row: AnalysisResult) -> dict[str, float]:
    payload = row.result or {}
    dimensions = payload.get("dimensions") or {}
    scores: dict[str, float] = {}
    for name in DIMENSIONS:
        dimension = dimensions.get(name) or {}
        raw = dimension.get("score") if isinstance(dimension, dict) else None
        if raw is None:
            continue
        try:
            scores[name] = float(raw)
        except (TypeError, ValueError):
            continue
    return scores


def _needs_review(row: AnalysisResult) -> bool:
    return bool((row.result or {}).get("needs_review"))


def _bands(rows: list[AnalysisResult]) -> ScoreBands:
    counts = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for row in rows:
        level = quality_level_for(_score_of(row))
        key = getattr(level, "value", str(level))
        if key in counts:
            counts[key] += 1
    return ScoreBands(**counts)


def _dimension_averages(rows: list[AnalysisResult]) -> dict[str, float]:
    totals: dict[str, list[float]] = {name: [] for name in DIMENSIONS}
    for row in rows:
        for name, score in _dimension_scores(row).items():
            totals[name].append(score)
    return {name: round(sum(values) / len(values), 2) for name, values in totals.items() if values}


def _average(rows: list[AnalysisResult]) -> float:
    if not rows:
        return 0.0
    return round(sum(_score_of(row) for row in rows) / len(rows), 2)


def _overview(task: Task, rows: list[AnalysisResult]) -> RunOverview:
    return RunOverview(
        task_id=task.id,
        status=task.status,
        completed_at=task.completed_at,
        sample_count=len(rows),
        avg_overall_score=_average(rows),
        needs_review=sum(1 for row in rows if _needs_review(row)),
        dimension_averages=_dimension_averages(rows),
        bands=_bands(rows),
    )


def _issue_counter(rows: list[AnalysisResult]) -> dict[str, tuple[int, str]]:
    """归一化后的问题文本 -> (出现次数, 首次出现的原文)。"""
    counter: dict[str, tuple[int, str]] = {}
    for row in rows:
        dimensions = (row.result or {}).get("dimensions") or {}
        for name in DIMENSIONS:
            for issue in (dimensions.get(name) or {}).get("issues") or []:
                text = str(issue).strip()
                if not text:
                    continue
                key = _WHITESPACE.sub("", text).lower()
                count, original = counter.get(key, (0, text))
                counter[key] = (count + 1, original)
    return counter


def _issue_diff(
    base_rows: list[AnalysisResult], target_rows: list[AnalysisResult]
) -> tuple[list[str], list[str]]:
    base = _issue_counter(base_rows)
    target = _issue_counter(target_rows)
    added = sorted(
        ((count, original) for key, (count, original) in target.items() if key not in base),
        key=lambda item: (-item[0], item[1]),
    )
    removed = sorted(
        ((count, original) for key, (count, original) in base.items() if key not in target),
        key=lambda item: (-item[0], item[1]),
    )
    return (
        [f"{original}（{count} 条）" for count, original in added[:MAX_ISSUES]],
        [f"{original}（{count} 条）" for count, original in removed[:MAX_ISSUES]],
    )


def _dialogue_deltas(
    base_rows: list[AnalysisResult], target_rows: list[AnalysisResult]
) -> tuple[list[DialogueDelta], list[DialogueDelta], int, int]:
    """按 data_id 对齐同一条对话，返回 (退步, 进步, 新增条数, 消失条数)。"""
    base = {row.data_id: _score_of(row) for row in base_rows if row.data_id is not None}
    target = {row.data_id: _score_of(row) for row in target_rows if row.data_id is not None}

    deltas = [
        DialogueDelta(
            data_id=data_id,
            base_score=round(base[data_id], 2),
            target_score=round(target[data_id], 2),
            delta=round(target[data_id] - base[data_id], 2),
        )
        for data_id in base.keys() & target.keys()
    ]
    regressions = sorted(
        (item for item in deltas if item.delta <= -MIN_REPORTED_DELTA),
        key=lambda item: item.delta,
    )[:TOP_DELTAS]
    improvements = sorted(
        (item for item in deltas if item.delta >= MIN_REPORTED_DELTA),
        key=lambda item: item.delta,
        reverse=True,
    )[:TOP_DELTAS]
    added = len(target.keys() - base.keys())
    removed = len(base.keys() - target.keys())
    return regressions, improvements, added, removed


def _band_delta(base: ScoreBands, target: ScoreBands) -> ScoreBands:
    return ScoreBands(
        excellent=target.excellent - base.excellent,
        good=target.good - base.good,
        fair=target.fair - base.fair,
        poor=target.poor - base.poor,
    )


def _category_counts(rows: list[AnalysisResult]) -> dict[str, int]:
    """按问题分类聚合（#6）：旧数据没有 issue_items 时返回空字典。"""
    counts: dict[str, int] = {}
    for row in rows:
        items = (row.result or {}).get("issue_items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "other")
            counts[category] = counts.get(category, 0) + 1
    return counts


def _category_deltas(
    base_rows: list[AnalysisResult], target_rows: list[AnalysisResult]
) -> list[IssueCategoryDelta]:
    base = _category_counts(base_rows)
    target = _category_counts(target_rows)
    categories = sorted(
        base.keys() | target.keys(),
        key=lambda key: (-(target.get(key, 0) + base.get(key, 0)), key),
    )
    return [
        IssueCategoryDelta(
            category=category,
            label=ISSUE_CATEGORY_LABELS.get(category, category),
            base=base.get(category, 0),
            target=target.get(category, 0),
            delta=target.get(category, 0) - base.get(category, 0),
        )
        for category in categories
    ]


def build_comparison(
    base_task: Task,
    base_rows: list[AnalysisResult],
    target_task: Task,
    target_rows: list[AnalysisResult],
) -> RunComparison:
    """纯计算：两个批次的对比结果（不碰数据库，便于单测）。"""
    base_overview = _overview(base_task, base_rows)
    target_overview = _overview(target_task, target_rows)

    dimension_names = [
        name
        for name in DIMENSIONS
        if name in base_overview.dimension_averages or name in target_overview.dimension_averages
    ]
    dimensions = [
        DimensionDelta(
            name=name,
            base=base_overview.dimension_averages.get(name, 0.0),
            target=target_overview.dimension_averages.get(name, 0.0),
            delta=round(
                target_overview.dimension_averages.get(name, 0.0)
                - base_overview.dimension_averages.get(name, 0.0),
                2,
            ),
        )
        for name in dimension_names
    ]

    regressions, improvements, added, removed = _dialogue_deltas(base_rows, target_rows)
    issues_added, issues_removed = _issue_diff(base_rows, target_rows)

    return RunComparison(
        base=base_overview,
        target=target_overview,
        delta=RunDelta(
            avg_overall_score=round(
                target_overview.avg_overall_score - base_overview.avg_overall_score, 2
            ),
            sample_count=target_overview.sample_count - base_overview.sample_count,
            needs_review=target_overview.needs_review - base_overview.needs_review,
            dimension_averages={item.name: item.delta for item in dimensions},
            bands=_band_delta(base_overview.bands, target_overview.bands),
        ),
        dimensions=dimensions,
        regressions=regressions,
        improvements=improvements,
        added_items=added,
        removed_items=removed,
        issues_added=issues_added,
        issues_removed=issues_removed,
        categories=_category_deltas(base_rows, target_rows),
    )


def _evaluated_of(task: Task) -> int | None:
    raw = (task.result or {}).get("evaluated")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    return None


# --------------------------------------------------------------------------- 数据库入口


async def _datasource_or_404(
    session: AsyncSession, datasource_id: uuid.UUID, user: User
) -> DataSource:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)
    return datasource


async def _task_or_404(session: AsyncSession, datasource_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = await session.get(Task, task_id)
    if task is None or task.datasource_id != datasource_id:
        raise AIInsightHubException(
            "Run not found",
            code=FrameworkErrorCode.HTTP_ERROR,
            status_code=404,
        )
    return task


async def list_runs(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    task_type: str = EVALUATE_TASK_TYPE,
    limit: int = DEFAULT_RUN_LIMIT,
) -> list[RunItem]:
    """按时间倒序列出批次（默认只看评估），并带上每批的样本数与平均分。"""
    await _datasource_or_404(session, datasource_id, user)

    limit = max(1, min(limit, MAX_RUN_LIMIT))
    tasks = list(
        (
            await session.execute(
                select(Task)
                .where(
                    Task.datasource_id == datasource_id,
                    Task.task_type == task_type,
                )
                .order_by(Task.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    aggregates = await analysis_repo.aggregate_by_task(
        session, [task.id for task in tasks], analysis_type="quality"
    )

    items: list[RunItem] = []
    for task in tasks:
        sample_count, avg_score = aggregates.get(task.id, (0, 0.0))
        raw_needs_review = (task.result or {}).get("needs_review")
        needs_review = (
            int(raw_needs_review)
            if isinstance(raw_needs_review, (int, float)) and not isinstance(raw_needs_review, bool)
            else None
        )
        items.append(
            RunItem(
                task_id=task.id,
                task_type=task.task_type,
                status=task.status,
                created_at=task.created_at,
                completed_at=task.completed_at,
                sample_count=sample_count,
                avg_overall_score=round(avg_score, 2) if sample_count else None,
                evaluated=_evaluated_of(task),
                needs_review=needs_review,
            )
        )
    return items


async def compare_runs(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    base_task_id: uuid.UUID,
    target_task_id: uuid.UUID,
) -> RunComparison:
    """对比两个评估批次（target 相对 base）。"""
    await _datasource_or_404(session, datasource_id, user)

    if base_task_id == target_task_id:
        raise AIInsightHubException(
            "Base and target run are the same task",
            code=FrameworkErrorCode.HTTP_ERROR,
            status_code=422,
        )

    base_task = await _task_or_404(session, datasource_id, base_task_id)
    target_task = await _task_or_404(session, datasource_id, target_task_id)

    for task in (base_task, target_task):
        if task.task_type != EVALUATE_TASK_TYPE:
            raise AIInsightHubException(
                "Only evaluation runs can be compared",
                code=FrameworkErrorCode.HTTP_ERROR,
                status_code=422,
            )
        if task.status != "completed":
            raise AIInsightHubException(
                f"Run {task.id} is {task.status}; only completed runs can be compared",
                code=FrameworkErrorCode.HTTP_ERROR,
                status_code=409,
            )

    base_rows = await analysis_repo.list_for_task(session, base_task.id, analysis_type="quality")
    target_rows = await analysis_repo.list_for_task(
        session, target_task.id, analysis_type="quality"
    )
    if not base_rows or not target_rows:
        # 历史批次（迁移 016 之前）没有 task_id 归属，无法对比
        raise AIInsightHubException(
            "Run has no results linked to it (legacy runs created before batch tracking "
            "cannot be compared; re-run the evaluation)",
            code=FrameworkErrorCode.HTTP_ERROR,
            status_code=409,
        )

    return build_comparison(base_task, base_rows, target_task, target_rows)


# --------------------------------------------------------------------------- 洞察对比（#3）


def _pain_point_map(payload: dict) -> dict[str, str]:
    """痛点 → {归一化文本: 原文}；兼容 dict 的多种字段名与纯字符串。"""
    mapping: dict[str, str] = {}
    for item in payload.get("pain_points") or []:
        if isinstance(item, dict):
            text = str(
                item.get("pain_point")
                or item.get("issue")
                or item.get("description")
                or item.get("topic")
                or ""
            ).strip()
            if not text:
                text = str(item)[:120]
        else:
            text = str(item).strip()
        if text:
            mapping[_WHITESPACE.sub("", text).lower()] = text
    return mapping


def build_insight_comparison(
    base_task: Task,
    base_payload: dict,
    target_task: Task,
    target_payload: dict,
) -> InsightComparison:
    """两次洞察的对比：情感占比、意图分布、痛点增减（纯计算，便于单测）。"""
    base_sentiment = base_payload.get("sentiment_distribution") or {}
    target_sentiment = target_payload.get("sentiment_distribution") or {}
    sentiment = [
        InsightMetric(
            name=str(name),
            base=round(float(base_sentiment.get(name, 0) or 0), 4),
            target=round(float(target_sentiment.get(name, 0) or 0), 4),
            delta=round(
                float(target_sentiment.get(name, 0) or 0) - float(base_sentiment.get(name, 0) or 0),
                4,
            ),
        )
        for name in sorted(base_sentiment.keys() | target_sentiment.keys())
    ]

    base_intents = base_payload.get("intent_distribution") or {}
    target_intents = target_payload.get("intent_distribution") or {}
    intents = [
        InsightMetric(
            name=str(name),
            base=float(base_intents.get(name, 0) or 0),
            target=float(target_intents.get(name, 0) or 0),
            delta=float(target_intents.get(name, 0) or 0) - float(base_intents.get(name, 0) or 0),
        )
        for name in sorted(
            base_intents.keys() | target_intents.keys(),
            key=lambda key: -(
                float(target_intents.get(key, 0) or 0) + float(base_intents.get(key, 0) or 0)
            ),
        )[:8]
    ]

    base_pains = _pain_point_map(base_payload)
    target_pains = _pain_point_map(target_payload)
    return InsightComparison(
        base_task_id=base_task.id,
        target_task_id=target_task.id,
        base_completed_at=base_task.completed_at,
        target_completed_at=target_task.completed_at,
        sentiment=sentiment,
        intents=intents,
        pain_points_added=[target_pains[key] for key in target_pains.keys() - base_pains.keys()],
        pain_points_removed=[base_pains[key] for key in base_pains.keys() - target_pains.keys()],
    )


async def compare_insights(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    base_task_id: uuid.UUID,
    target_task_id: uuid.UUID,
) -> InsightComparison:
    """对比两次洞察分析（task_type=analyze，各取最新一条 insight 结果）。"""
    await _datasource_or_404(session, datasource_id, user)
    if base_task_id == target_task_id:
        raise AIInsightHubException(
            "Base and target run are the same task",
            code=FrameworkErrorCode.HTTP_ERROR,
            status_code=422,
        )

    base_task = await _task_or_404(session, datasource_id, base_task_id)
    target_task = await _task_or_404(session, datasource_id, target_task_id)
    for task in (base_task, target_task):
        if task.task_type != "analyze":
            raise AIInsightHubException(
                "Only insight runs can be compared here",
                code=FrameworkErrorCode.HTTP_ERROR,
                status_code=422,
            )
        if task.status != "completed":
            raise AIInsightHubException(
                f"Run {task.id} is {task.status}; only completed runs can be compared",
                code=FrameworkErrorCode.HTTP_ERROR,
                status_code=409,
            )

    base_rows = await analysis_repo.list_for_task(session, base_task.id, analysis_type="insight")
    target_rows = await analysis_repo.list_for_task(
        session, target_task.id, analysis_type="insight"
    )
    if not base_rows or not target_rows:
        raise AIInsightHubException(
            "Insight run has no results (legacy runs created before batch tracking cannot "
            "be compared; re-run the analysis)",
            code=FrameworkErrorCode.HTTP_ERROR,
            status_code=409,
        )

    return build_insight_comparison(
        base_task, base_rows[0].result or {}, target_task, target_rows[0].result or {}
    )


__all__ = [
    "build_comparison",
    "build_insight_comparison",
    "compare_insights",
    "compare_runs",
    "list_runs",
]
