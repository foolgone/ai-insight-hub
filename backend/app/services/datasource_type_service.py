"""数据源类型字典服务（增删改查 + 使用量统计）。

约束：
- ``code`` 不可修改（``data_sources.type`` 直接存 code）；
- 内置类型（``is_system``）不可删除，但可以改名/停用；
- 仍被数据源引用的类型不可删除（409），避免历史数据失去标签；
- 新建/编辑数据源时通过 ``ensure_usable`` 校验类型存在且启用。
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DataSourceTypeInUseError,
    DataSourceTypeInvalidError,
    DataSourceTypeNotFoundError,
)
from app.models import DataSource, DataSourceType
from app.schemas.datasource_type import DataSourceTypeCreate, DataSourceTypeUpdate

__all__ = [
    "create",
    "delete",
    "ensure_usable",
    "get",
    "list_types",
    "update",
]

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,49}$")


def _normalize_code(raw: str | None) -> str:
    """校验/生成类型标识。"""
    code = (raw or "").strip().lower()
    if not code:
        return f"t_{uuid.uuid4().hex[:8]}"
    if not CODE_PATTERN.match(code):
        raise DataSourceTypeInvalidError(
            "类型标识只能包含小写字母、数字和下划线，且以字母开头（2-50 位）"
        )
    return code


async def _usage_count(session: AsyncSession, code: str) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(DataSource)
            .where(
                DataSource.type == code,
                DataSource.deleted_at.is_(None),
            )
        )
        or 0
    )


async def list_types(
    session: AsyncSession, *, include_inactive: bool = False
) -> list[tuple[DataSourceType, int]]:
    """返回 [(类型, 使用中的数据源数量)]，按 sort_order 升序。"""
    stmt = (
        select(DataSourceType, func.count(DataSource.id))
        .outerjoin(
            DataSource,
            and_(
                DataSource.type == DataSourceType.code,
                DataSource.deleted_at.is_(None),
            ),
        )
        .group_by(DataSourceType.id)
        .order_by(DataSourceType.sort_order.asc(), DataSourceType.created_at.asc())
    )
    if not include_inactive:
        stmt = stmt.where(DataSourceType.is_active.is_(True))
    rows = (await session.execute(stmt)).all()
    return [(row[0], int(row[1])) for row in rows]


async def get(session: AsyncSession, type_id: uuid.UUID) -> DataSourceType:
    row = await session.get(DataSourceType, type_id)
    if row is None:
        raise DataSourceTypeNotFoundError(details={"type_id": str(type_id)})
    return row


async def ensure_usable(session: AsyncSession, code: str) -> DataSourceType:
    """校验类型存在且启用；未知/停用 → 400。"""
    row = await session.scalar(
        select(DataSourceType).where(DataSourceType.code == code)
    )
    if row is None:
        raise DataSourceTypeInvalidError(f"未知的数据源类型：{code}")
    if not row.is_active:
        raise DataSourceTypeInvalidError(f"数据源类型已停用：{row.label}")
    return row


async def _next_sort_order(session: AsyncSession) -> int:
    current = await session.scalar(select(func.max(DataSourceType.sort_order)))
    return int(current or 0) + 10


async def create(session: AsyncSession, data: DataSourceTypeCreate) -> DataSourceType:
    code = _normalize_code(data.code)
    exists = await session.scalar(
        select(DataSourceType.id).where(DataSourceType.code == code)
    )
    if exists is not None:
        raise DataSourceTypeInvalidError(f"类型标识已存在：{code}")

    row = DataSourceType(
        code=code,
        label=data.label.strip(),
        description=(data.description or "").strip() or None,
        sort_order=data.sort_order if data.sort_order is not None else await _next_sort_order(session),
        is_system=False,
        is_active=True,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def update(
    session: AsyncSession, type_id: uuid.UUID, data: DataSourceTypeUpdate
) -> DataSourceType:
    row = await get(session, type_id)
    payload = data.model_dump(exclude_unset=True)

    if payload.get("label") is not None:
        row.label = payload["label"].strip()
    if "description" in payload:
        row.description = (payload["description"] or "").strip() or None
    if payload.get("sort_order") is not None:
        row.sort_order = int(payload["sort_order"])
    if payload.get("is_active") is not None:
        row.is_active = bool(payload["is_active"])

    await session.flush()
    await session.refresh(row)
    return row


async def delete(session: AsyncSession, type_id: uuid.UUID) -> None:
    row = await get(session, type_id)
    if row.is_system:
        raise DataSourceTypeInvalidError("内置类型不可删除，可改为停用")
    usage = await _usage_count(session, row.code)
    if usage:
        raise DataSourceTypeInUseError(
            f"该类型仍被 {usage} 个数据源使用，无法删除",
            details={"usage_count": usage},
        )
    await session.delete(row)
    await session.flush()
