"""``analysis_results`` 仓储：质量评估 / 洞察 / 摘要等分析结果的写入与读取。"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisResult


def _base(datasource_id: uuid.UUID, analysis_type: str | None = None) -> Select:
    stmt = select(AnalysisResult).where(AnalysisResult.datasource_id == datasource_id)
    if analysis_type is not None:
        stmt = stmt.where(AnalysisResult.analysis_type == analysis_type)
    return stmt


async def add(session: AsyncSession, result: AnalysisResult) -> AnalysisResult:
    """写入一条分析结果（由调用方负责 flush/commit）。"""
    session.add(result)
    return result


async def list_by_type(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    analysis_type: str,
    *,
    limit: int = 100,
) -> list[AnalysisResult]:
    stmt = (
        _base(datasource_id, analysis_type).order_by(AnalysisResult.created_at.desc()).limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_for_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    *,
    analysis_type: str | None = None,
) -> list[AnalysisResult]:
    """取某个批次（任务）产生的全部结果，按对话顺序返回，供批次对比使用。"""
    stmt = select(AnalysisResult).where(AnalysisResult.task_id == task_id)
    if analysis_type is not None:
        stmt = stmt.where(AnalysisResult.analysis_type == analysis_type)
    stmt = stmt.order_by(AnalysisResult.data_id)
    return list((await session.execute(stmt)).scalars().all())


async def aggregate_by_task(
    session: AsyncSession,
    task_ids: list[uuid.UUID],
    analysis_type: str = "quality",
) -> dict[uuid.UUID, tuple[int, float]]:
    """按批次聚合 ``(样本数, 平均总分)``；没有结果的批次不出现在返回值里。"""
    if not task_ids:
        return {}
    overall = cast(AnalysisResult.result["overall_score"].astext, Float)
    rows = (
        await session.execute(
            select(
                AnalysisResult.task_id,
                func.count().label("total"),
                func.coalesce(func.avg(overall), 0).label("avg_score"),
            )
            .where(
                AnalysisResult.task_id.in_(task_ids),
                AnalysisResult.analysis_type == analysis_type,
            )
            .group_by(AnalysisResult.task_id)
        )
    ).all()
    return {
        row.task_id: (int(row.total or 0), float(row.avg_score or 0))
        for row in rows
        if row.task_id is not None
    }


__all__ = ["add", "aggregate_by_task", "list_by_type", "list_for_task"]
