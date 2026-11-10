"""``raw_data`` 仓储：上传记录（原始文件 / 文本 / 媒体）的写入与读取。"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawData


async def add(session: AsyncSession, raw: RawData) -> RawData:
    """写入一条上传记录（调用方负责 flush/commit）。"""
    session.add(raw)
    return raw


async def get(session: AsyncSession, raw_id: uuid.UUID) -> RawData | None:
    return await session.get(RawData, raw_id)


async def list_for_datasource(session: AsyncSession, datasource_id: uuid.UUID) -> list[RawData]:
    stmt = (
        select(RawData)
        .where(RawData.datasource_id == datasource_id)
        .order_by(RawData.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


__all__ = ["add", "get", "list_for_datasource"]
