"""``cleaned_data`` 仓储：对话清洗结果的读写。"""
from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import PaginationParams, paginate
from app.models import CleanedData
from app.schemas.base import Pagination

#: 允许排序的字段白名单（不在白名单内的 sort 会被忽略）
SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "timestamp": CleanedData.timestamp,
    "quality_score": CleanedData.quality_score,
    "created_at": CleanedData.created_at,
}


def _filtered(
    stmt: Select,
    *,
    datasource_id: uuid.UUID,
    quality_score_min: float | None = None,
    quality_score_max: float | None = None,
    has_issues: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select:
    stmt = stmt.where(CleanedData.datasource_id == datasource_id)
    if quality_score_min is not None:
        stmt = stmt.where(CleanedData.quality_score >= quality_score_min)
    if quality_score_max is not None:
        stmt = stmt.where(CleanedData.quality_score <= quality_score_max)
    if has_issues is True:
        stmt = stmt.where(func.cardinality(CleanedData.issues) > 0)
    elif has_issues is False:
        stmt = stmt.where(
            (CleanedData.issues.is_(None)) | (func.cardinality(CleanedData.issues) == 0)
        )
    if date_from is not None:
        stmt = stmt.where(CleanedData.timestamp >= date_from)
    if date_to is not None:
        stmt = stmt.where(CleanedData.timestamp <= date_to)
    return stmt


async def list_for_datasource(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    *,
    params: PaginationParams,
    quality_score_min: float | None = None,
    quality_score_max: float | None = None,
    has_issues: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[CleanedData], Pagination]:
    """数据源下的对话列表（带质量分 / 问题 / 时间范围过滤）。"""
    stmt = _filtered(
        select(CleanedData),
        datasource_id=datasource_id,
        quality_score_min=quality_score_min,
        quality_score_max=quality_score_max,
        has_issues=has_issues,
        date_from=date_from,
        date_to=date_to,
    )
    return await paginate(session, stmt, params, sortable=SORTABLE)


async def get(session: AsyncSession, data_id: uuid.UUID) -> CleanedData | None:
    return await session.get(CleanedData, data_id)


async def list_for_analysis(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    *,
    limit: int,
    newest_first: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CleanedData]:
    """取一段对话用于 AI 分析（洞察 / 知识提取）。

    ``newest_first=True`` 时按创建时间倒序（知识提取看最近的对话），
    否则按时间戳正序（洞察按时间线讲）。
    """
    stmt = select(CleanedData).where(CleanedData.datasource_id == datasource_id)
    if date_from is not None:
        stmt = stmt.where(CleanedData.timestamp >= date_from)
    if date_to is not None:
        stmt = stmt.where(CleanedData.timestamp <= date_to)
    if newest_first:
        stmt = stmt.order_by(CleanedData.created_at.desc())
    else:
        stmt = stmt.order_by(CleanedData.timestamp.asc())
    return list((await session.execute(stmt.limit(limit))).scalars().all())


async def load_evaluable(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    data_ids: Sequence[uuid.UUID] | None = None,
    limit: int,
) -> tuple[int, list[CleanedData]]:
    """加载可评估对话：``ai_response`` 非空（单声道转写记录没有客服回复）。

    返回 ``(总数, 本次要评估的批次)``；总数用于进度展示。
    """
    filters: list[Any] = [CleanedData.datasource_id == datasource_id]
    if data_ids:
        filters.append(CleanedData.id.in_(data_ids))

    total = int(
        await session.scalar(select(func.count()).select_from(CleanedData).where(*filters)) or 0
    )
    stmt = (
        select(CleanedData)
        .where(*filters, func.trim(CleanedData.ai_response) != "")
        .order_by(CleanedData.created_at.asc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return total, rows


async def count_for_datasource(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(CleanedData)
            .where(CleanedData.datasource_id == datasource_id)
        )
        or 0
    )


async def insert_ignore_conflicts(
    session: AsyncSession, rows: Iterable[Mapping[str, Any]]
) -> list[tuple[uuid.UUID, float | None]]:
    """批量写入，命中唯一索引 ``(raw_data_id, dialogue_id)`` 的行直接跳过。

    返回真正插入的 ``(id, quality_score)``，调用方据此统计新增与均分。
    """
    payload = list(rows)
    if not payload:
        return []
    stmt = (
        # 用 Table 而非 ORM 实体做批量 upsert（避免 ORM 批量语义）；
        # mypy 把 __table__ 推断成 FromClause，这里显式忽略参数类型
        pg_insert(CleanedData.__table__)  # type: ignore[arg-type]
        .values(payload)
        .on_conflict_do_nothing(index_elements=["raw_data_id", "dialogue_id"])
        .returning(CleanedData.__table__.c.id, CleanedData.__table__.c.quality_score)
    )
    inserted = (await session.execute(stmt)).all()
    return [(row.id, row.quality_score) for row in inserted]


__all__ = [
    "SORTABLE",
    "count_for_datasource",
    "get",
    "insert_ignore_conflicts",
    "list_for_analysis",
    "list_for_datasource",
    "load_evaluable",
]
