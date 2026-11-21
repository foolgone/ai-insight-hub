"""``qa_datasets`` 仓储：数据集 / 版本 / 条目的读写。

只负责 SQL；「发布后不可变」「导入校验」「checksum」等规则在
``app.services.qa_dataset_service``。
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.pagination import PaginationParams
from app.models import QaDataset, QaDatasetItem, QaDatasetVersion
from app.repositories.pagination import paginate
from app.schemas.base import Pagination

SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "created_at": QaDataset.created_at,
    "name": QaDataset.name,
}

ITEM_SORTABLE: Mapping[str, InstrumentedAttribute] = {
    "created_at": QaDatasetItem.created_at,
    "item_key": QaDatasetItem.item_key,
}


# --------------------------------------------------------------------------- 数据集


async def add_dataset(session: AsyncSession, dataset: QaDataset) -> QaDataset:
    session.add(dataset)
    await session.flush()
    await session.refresh(dataset)
    return dataset


async def get_dataset(session: AsyncSession, dataset_id: uuid.UUID) -> QaDataset | None:
    return await session.get(QaDataset, dataset_id)


async def get_dataset_by_name(
    session: AsyncSession, user_id: uuid.UUID, name: str
) -> QaDataset | None:
    return await session.scalar(
        select(QaDataset).where(QaDataset.user_id == user_id, QaDataset.name == name)
    )


async def list_datasets(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    keyword: str | None,
    params: PaginationParams,
) -> tuple[list[QaDataset], Pagination]:
    stmt: Select = select(QaDataset)
    if user_id is not None:
        stmt = stmt.where(QaDataset.user_id == user_id)
    if keyword:
        stmt = stmt.where(QaDataset.name.ilike(f"%{keyword}%"))
    return await paginate(session, stmt, params, sortable=SORTABLE)


# --------------------------------------------------------------------------- 版本


async def add_version(session: AsyncSession, version: QaDatasetVersion) -> QaDatasetVersion:
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def get_version(session: AsyncSession, version_id: uuid.UUID) -> QaDatasetVersion | None:
    return await session.get(QaDatasetVersion, version_id)


async def list_versions(session: AsyncSession, dataset_id: uuid.UUID) -> list[QaDatasetVersion]:
    rows = await session.execute(
        select(QaDatasetVersion)
        .where(QaDatasetVersion.dataset_id == dataset_id)
        .order_by(QaDatasetVersion.version.desc())
    )
    return list(rows.scalars().all())


async def next_version_number(session: AsyncSession, dataset_id: uuid.UUID) -> int:
    current = await session.scalar(
        select(func.coalesce(func.max(QaDatasetVersion.version), 0)).where(
            QaDatasetVersion.dataset_id == dataset_id
        )
    )
    return int(current or 0) + 1


# --------------------------------------------------------------------------- 条目


async def add_items(session: AsyncSession, rows: Sequence[QaDatasetItem]) -> None:
    session.add_all(list(rows))
    await session.flush()


async def get_item(session: AsyncSession, item_id: uuid.UUID) -> QaDatasetItem | None:
    return await session.get(QaDatasetItem, item_id)


async def list_items(
    session: AsyncSession,
    *,
    version_id: uuid.UUID,
    split: str | None,
    category: str | None,
    keyword: str | None,
    params: PaginationParams,
) -> tuple[list[QaDatasetItem], Pagination]:
    stmt: Select = select(QaDatasetItem).where(QaDatasetItem.version_id == version_id)
    if split:
        stmt = stmt.where(QaDatasetItem.split == split)
    if category:
        stmt = stmt.where(QaDatasetItem.category == category)
    if keyword:
        stmt = stmt.where(QaDatasetItem.query.ilike(f"%{keyword}%"))
    return await paginate(session, stmt, params, sortable=ITEM_SORTABLE)


async def list_all_items(session: AsyncSession, version_id: uuid.UUID) -> list[QaDatasetItem]:
    """按 item_key 排序返回全部条目（checksum 与复制版本用，不分页）。"""
    rows = await session.execute(
        select(QaDatasetItem)
        .where(QaDatasetItem.version_id == version_id)
        .order_by(QaDatasetItem.item_key)
    )
    return list(rows.scalars().all())


async def existing_item_keys(session: AsyncSession, version_id: uuid.UUID) -> set[str]:
    rows = await session.execute(
        select(QaDatasetItem.item_key).where(QaDatasetItem.version_id == version_id)
    )
    return set(rows.scalars().all())


async def delete_item(session: AsyncSession, item: QaDatasetItem) -> None:
    await session.delete(item)
    await session.flush()


async def count_items(session: AsyncSession, version_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(QaDatasetItem)
            .where(QaDatasetItem.version_id == version_id)
        )
        or 0
    )


async def counts_by_split(session: AsyncSession, version_id: uuid.UUID) -> dict[str, int]:
    rows = await session.execute(
        select(QaDatasetItem.split, func.count())
        .where(QaDatasetItem.version_id == version_id)
        .group_by(QaDatasetItem.split)
    )
    return {str(split): int(count) for split, count in rows.all()}


async def counts_by_category(
    session: AsyncSession, version_id: uuid.UUID, *, limit: int = 20
) -> dict[str, int]:
    rows = await session.execute(
        select(QaDatasetItem.category, func.count())
        .where(QaDatasetItem.version_id == version_id)
        .group_by(QaDatasetItem.category)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return {str(category or "未分类"): int(count) for category, count in rows.all()}


async def count_with_evidence(session: AsyncSession, version_id: uuid.UUID) -> int:
    """gold_evidence 非空数组的条目数（JSONB 数组长度 > 0）。"""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(QaDatasetItem)
            .where(
                QaDatasetItem.version_id == version_id,
                func.jsonb_array_length(QaDatasetItem.gold_evidence) > 0,
            )
        )
        or 0
    )


async def update_version_counts(
    session: AsyncSession, version: QaDatasetVersion, *, item_count: int
) -> None:
    version.item_count = item_count
    await session.flush()


__all__: list[str] = [
    "ITEM_SORTABLE",
    "SORTABLE",
    "add_dataset",
    "add_items",
    "add_version",
    "count_items",
    "count_with_evidence",
    "counts_by_category",
    "counts_by_split",
    "delete_item",
    "existing_item_keys",
    "get_dataset",
    "get_dataset_by_name",
    "get_item",
    "get_version",
    "list_all_items",
    "list_datasets",
    "list_items",
    "list_versions",
    "next_version_number",
    "update_version_counts",
]
