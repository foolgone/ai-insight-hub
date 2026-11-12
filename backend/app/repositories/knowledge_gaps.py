"""``knowledge_gaps`` 仓储：盲区台账的写入、查询与状态流转。"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeGap

_WHITESPACE = re.compile(r"\s+")


def question_key(question: str) -> str:
    """归一化问题 → md5（用于同数据源内去重，避免长文本做唯一索引）。"""
    normalized = _WHITESPACE.sub("", str(question or "")).lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def upsert_many(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    gaps: Iterable[Mapping[str, Any]],
    task_id: uuid.UUID | None = None,
) -> int:
    """批量写入盲区台账：已存在则累加 ``hit_count``、刷新 ``last_seen``。

    状态不因重跑而回退（``adopted`` / ``ignored`` 保持不变）。
    """
    rows: list[dict[str, Any]] = []
    dedup: dict[str, dict[str, Any]] = {}
    for gap in gaps:
        question = str(gap.get("question") or "").strip()
        if not question:
            continue
        key = question_key(question)
        existing = dedup.get(key)
        frequency = int(gap.get("frequency") or 1)
        if existing is not None:
            existing["hit_count"] += frequency
            continue
        dedup[key] = {
            "id": uuid.uuid4(),
            "datasource_id": datasource_id,
            "question": question[:2000],
            "question_key": key,
            "status": "open",
            "faq_id": None,
            "hit_count": frequency,
            "priority": str(gap.get("priority") or "") or None,
            "source_task_id": task_id,
            "first_seen": _now(),
            "last_seen": _now(),
        }
    rows = list(dedup.values())
    if not rows:
        return 0

    table = KnowledgeGap.__table__
    stmt = pg_insert(table).values(rows)  # type: ignore[arg-type]
    stmt = stmt.on_conflict_do_update(
        index_elements=["datasource_id", "question_key"],
        set_={
            "hit_count": table.c.hit_count + stmt.excluded.hit_count,
            "question": stmt.excluded.question,
            # 新一轮没给优先级时保留原值，避免把人工/模型判定的 high 冲掉
            "priority": func.coalesce(stmt.excluded.priority, table.c.priority),
            "last_seen": func.now(),
            "source_task_id": stmt.excluded.source_task_id,
        },
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def list_for_datasource(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[KnowledgeGap]:
    stmt = select(KnowledgeGap).where(KnowledgeGap.datasource_id == datasource_id)
    if status is not None:
        stmt = stmt.where(KnowledgeGap.status == status)
    stmt = stmt.order_by(KnowledgeGap.hit_count.desc(), KnowledgeGap.last_seen.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get(session: AsyncSession, gap_id: uuid.UUID) -> KnowledgeGap | None:
    return await session.get(KnowledgeGap, gap_id)


async def count_by_status(session: AsyncSession, datasource_id: uuid.UUID) -> dict[str, int]:
    rows = (
        await session.execute(
            select(KnowledgeGap.status, func.count())
            .where(KnowledgeGap.datasource_id == datasource_id)
            .group_by(KnowledgeGap.status)
        )
    ).all()
    return {str(status): int(count) for status, count in rows}


__all__ = [
    "count_by_status",
    "get",
    "list_for_datasource",
    "question_key",
    "upsert_many",
]
