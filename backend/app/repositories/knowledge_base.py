"""``knowledge_base`` 仓储：FAQ 的读写与检索。

去重与状态流转的**规则**留在 ``knowledge_dedup`` / ``knowledge_status``，
这里只负责 SQL。
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import PaginationParams, paginate
from app.models import KnowledgeBase
from app.schemas.base import Pagination

SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "frequency": KnowledgeBase.frequency,
    "created_at": KnowledgeBase.created_at,
}


def _filtered(
    stmt: Select,
    *,
    datasource_id: uuid.UUID,
    category: str | None = None,
    min_frequency: int | None = None,
    status: str | None = None,
) -> Select:
    stmt = stmt.where(KnowledgeBase.datasource_id == datasource_id)
    if category:
        stmt = stmt.where(KnowledgeBase.category == category)
    if min_frequency is not None:
        stmt = stmt.where(KnowledgeBase.frequency >= min_frequency)
    if status:
        stmt = stmt.where(KnowledgeBase.status == status)
    return stmt


async def list_for_datasource(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    *,
    params: PaginationParams,
    category: str | None = None,
    min_frequency: int | None = None,
    status: str | None = None,
) -> tuple[list[KnowledgeBase], Pagination]:
    stmt = _filtered(
        select(KnowledgeBase),
        datasource_id=datasource_id,
        category=category,
        min_frequency=min_frequency,
        status=status,
    )
    return await paginate(session, stmt, params, sortable=SORTABLE)


async def get(session: AsyncSession, faq_id: uuid.UUID) -> KnowledgeBase | None:
    return await session.get(KnowledgeBase, faq_id)


async def existing_questions(session: AsyncSession, datasource_id: uuid.UUID) -> list[str]:
    """已提取的问题（排除种子数据），供提取 Agent 去重。"""
    rows = (
        (
            await session.execute(
                select(KnowledgeBase.question).where(
                    KnowledgeBase.datasource_id == datasource_id,
                    KnowledgeBase.is_seed.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    return [str(item) for item in rows]


async def nearest_questions(
    session: AsyncSession, datasource_id: uuid.UUID, *, query_vector: Sequence[float], limit: int
) -> list[str]:
    """按向量距离取最相近的已有问题（去重用）。"""
    stmt = (
        select(KnowledgeBase.question)
        .where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.is_seed.is_(False),
            KnowledgeBase.embedding.is_not(None),
        )
        .order_by(KnowledgeBase.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [str(item) for item in rows]


async def delete_seed(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    """删除种子知识（重新提取前清空）。"""
    result = await session.execute(
        delete(KnowledgeBase).where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.is_seed.is_(True),
        )
    )
    return int(result.rowcount or 0)


async def search(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    *,
    query: str,
    query_vector: Sequence[float] | None,
    limit: int,
) -> list[tuple[KnowledgeBase, float]]:
    """混合检索：trigram 0.4 + 向量 0.6（无向量时退化为纯 trigram）。"""
    trigram = func.similarity(KnowledgeBase.question, query)
    if query_vector is not None:
        vector_similarity = 1 - KnowledgeBase.embedding.cosine_distance(query_vector)
        score = trigram * 0.4 + func.coalesce(vector_similarity, 0.0) * 0.6
    else:
        score = trigram
    stmt = (
        select(KnowledgeBase, score.label("similarity"))
        .where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.status == "active",
        )
        .order_by(score.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [(faq, float(similarity or 0)) for faq, similarity in rows]


async def count_by_status(
    session: AsyncSession, datasource_id: uuid.UUID, *, status: str | None = None
) -> int:
    stmt = _filtered(
        select(func.count()).select_from(KnowledgeBase),
        datasource_id=datasource_id,
        status=status,
    )
    return int(await session.scalar(stmt) or 0)


async def count_by_source(
    session: AsyncSession, datasource_id: uuid.UUID, *, status: str = "active"
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(KnowledgeBase.source, func.count())
            .where(
                KnowledgeBase.datasource_id == datasource_id,
                KnowledgeBase.status == status,
            )
            .group_by(KnowledgeBase.source)
        )
    ).all()
    return {str(source): int(count) for source, count in rows}


__all__ = [
    "SORTABLE",
    "count_by_source",
    "count_by_status",
    "delete_seed",
    "existing_questions",
    "get",
    "list_for_datasource",
    "nearest_questions",
    "search",
]
