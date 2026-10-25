"""数据源服务（API 设计 §5；删除语义按计划 D-06）。

- 创建：按 ``users.quota.max_datasources`` 校验配额（默认 10）；
- 列表/详情：admin 全量，其余仅本人；
- 删除：默认软删（``deleted_at``），``force=true`` 物理删除并统计级联记录数。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_owner
from app.api.pagination import PaginationParams, paginate
from app.core.exceptions import (
    DataSourceNotFoundError,
    DataSourceQuotaExceededError,
)
from app.models import (
    AnalysisResult,
    CleanedData,
    DataSource,
    KnowledgeBase,
    RawData,
    Report,
    Task,
    User,
)
from app.schemas.base import Pagination
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate

DEFAULT_MAX_DATASOURCES = 10

# 级联相关表（force 删除时统计 deleted_records）
_RELATED_MODELS = (RawData, CleanedData, AnalysisResult, KnowledgeBase, Report, Task)

_SORTABLE = {"created_at": DataSource.created_at, "name": DataSource.name}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _quota_limit(user: User) -> int:
    quota = user.quota or {}
    try:
        return int(quota.get("max_datasources", DEFAULT_MAX_DATASOURCES))
    except (TypeError, ValueError):
        return DEFAULT_MAX_DATASOURCES


async def _get_or_404(session: AsyncSession, datasource_id: uuid.UUID, user: User) -> DataSource:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)
    return datasource


async def create(session: AsyncSession, *, user: User, data: DataSourceCreate) -> DataSource:
    used = int(
        await session.scalar(
            select(func.count())
            .select_from(DataSource)
            .where(
                DataSource.user_id == user.id,
                DataSource.deleted_at.is_(None),
            )
        )
        or 0
    )
    limit = _quota_limit(user)
    if used >= limit:
        raise DataSourceQuotaExceededError(details={"max_datasources": limit, "current": used})

    datasource = DataSource(
        name=data.name,
        description=data.description,
        type=data.type,
        user_id=user.id,
        config=data.config.model_dump(mode="json"),
    )
    session.add(datasource)
    await session.flush()
    await session.refresh(datasource)
    return datasource


async def list_datasources(
    session: AsyncSession,
    *,
    user: User,
    params: PaginationParams,
    status: str | None = None,
    data_source_type: str | None = None,
) -> tuple[list[DataSource], Pagination]:
    stmt = select(DataSource).where(DataSource.deleted_at.is_(None))
    if user.role != "admin":
        stmt = stmt.where(DataSource.user_id == user.id)
    if status:
        stmt = stmt.where(DataSource.status == status)
    if data_source_type:
        stmt = stmt.where(DataSource.type == data_source_type)
    return await paginate(session, stmt, params, sortable=_SORTABLE)


async def get(session: AsyncSession, *, user: User, datasource_id: uuid.UUID) -> DataSource:
    return await _get_or_404(session, datasource_id, user)


async def update(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    data: DataSourceUpdate,
) -> DataSource:
    datasource = await _get_or_404(session, datasource_id, user)
    payload = data.model_dump(exclude_unset=True)

    if payload.get("name") is not None:
        datasource.name = payload["name"]
    if "description" in payload:
        datasource.description = payload["description"]
    if data.config is not None:
        merged = dict(datasource.config or {})
        merged.update(data.config.model_dump(exclude_unset=True, mode="json"))
        datasource.config = merged

    datasource.updated_at = _now_naive()
    await session.flush()
    await session.refresh(datasource)
    return datasource


async def delete(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    force: bool = False,
) -> tuple[str, int]:
    datasource = await _get_or_404(session, datasource_id, user)

    if not force:
        datasource.deleted_at = _now_naive()
        await session.flush()
        return "Data source deleted successfully", 0

    deleted_records = 0
    for model in _RELATED_MODELS:
        column = getattr(model, "datasource_id", None)
        if column is None:
            continue
        deleted_records += int(
            await session.scalar(
                select(func.count()).select_from(model).where(column == datasource.id)
            )
            or 0
        )
    await session.delete(datasource)
    await session.flush()
    return "Data source deleted successfully", deleted_records


__all__ = [
    "DEFAULT_MAX_DATASOURCES",
    "create",
    "delete",
    "get",
    "list_datasources",
    "update",
]
