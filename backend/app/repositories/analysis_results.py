"""``analysis_results`` 仓储：质量评估 / 洞察 / 摘要等分析结果的写入与读取。"""
from __future__ import annotations

import uuid

from sqlalchemy import Select, select
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


__all__ = ["add", "list_by_type"]
