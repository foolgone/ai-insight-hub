"""知识库冷启动状态（B-501；10-知识库冷启动处理 §2）。

三态（按 active 知识条数）：
- ``cold``    0 条：无可用知识，提示上传数据/种子库/提取；
- ``warming`` 1-49 条：半冷启动，提示继续补充；
- ``ready``   ≥50 条：知识库就绪。
"""
from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase

COLD_START_THRESHOLD = 1
READY_THRESHOLD = 50


class KnowledgeStage(str, Enum):
    COLD = "cold"
    WARMING = "warming"
    READY = "ready"


def stage_for_count(count: int) -> KnowledgeStage:
    """按知识条数返回冷启动三态。"""
    if count < COLD_START_THRESHOLD:
        return KnowledgeStage.COLD
    if count < READY_THRESHOLD:
        return KnowledgeStage.WARMING
    return KnowledgeStage.READY


async def count_knowledge(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    *,
    status: str | None = "active",
) -> int:
    stmt = (
        select(func.count())
        .select_from(KnowledgeBase)
        .where(KnowledgeBase.datasource_id == datasource_id)
    )
    if status is not None:
        stmt = stmt.where(KnowledgeBase.status == status)
    return int(await session.scalar(stmt) or 0)


async def _count_by_source(session: AsyncSession, datasource_id: uuid.UUID) -> dict[str, int]:
    rows = (
        await session.execute(
            select(KnowledgeBase.source, func.count())
            .where(
                KnowledgeBase.datasource_id == datasource_id,
                KnowledgeBase.status == "active",
            )
            .group_by(KnowledgeBase.source)
        )
    ).all()
    counts = {"seed": 0, "extracted": 0, "manual": 0}
    for source, count in rows:
        counts[str(source)] = int(count)
    return counts


def _suggestion(stage: KnowledgeStage, total: int) -> str:
    if stage is KnowledgeStage.COLD:
        return "知识库为空：可初始化 12 条种子知识，或上传对话数据后执行知识提取"
    if stage is KnowledgeStage.WARMING:
        return f"已有 {total} 条知识，补充至 {READY_THRESHOLD} 条可进入就绪状态"
    return "知识库已就绪，可执行 FAQ 检索与报告生成"


async def get_knowledge_status(session: AsyncSession, datasource_id: uuid.UUID) -> dict:
    """返回冷启动状态摘要（API 三态提示用）。"""
    total = await count_knowledge(session, datasource_id)
    by_source = await _count_by_source(session, datasource_id)
    stage = stage_for_count(total)
    return {
        "datasource_id": str(datasource_id),
        "total": total,
        "seed": by_source["seed"],
        "extracted": by_source["extracted"],
        "manual": by_source["manual"],
        "stage": stage.value,
        "ready_threshold": READY_THRESHOLD,
        "suggestion": _suggestion(stage, total),
    }


__all__ = [
    "COLD_START_THRESHOLD",
    "READY_THRESHOLD",
    "KnowledgeStage",
    "count_knowledge",
    "get_knowledge_status",
    "stage_for_count",
]
