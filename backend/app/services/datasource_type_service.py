"""数据源类型字典服务（按用户隔离，多租户）。

约束：
- 所有读写都以 ``user_id`` 为边界：查不到别人的类型（越权一律 404，不暴露存在性）；
- ``code`` 在同一用户内唯一、不可修改（``data_sources.type`` 直接存 code）；
- 首次访问时为用户播种 4 个默认类型（``is_system=True``），可改名/停用但不可删除；
- 仍被该用户的数据源引用的类型不可删除（409）；
- 不允许把「最后一个启用类型」删掉或停用，否则用户无法新建数据源。
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DataSourceTypeInUseError,
    DataSourceTypeInvalidError,
    DataSourceTypeNotFoundError,
)
from app.models import DataSource, DataSourceType
from app.schemas.datasource_type import DataSourceTypeCreate, DataSourceTypeUpdate

__all__ = [
    "DEFAULT_TYPES",
    "create",
    "delete",
    "ensure_user_defaults",
    "ensure_usable",
    "get",
    "list_types",
    "update",
]

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,49}$")

# 新用户首次访问时播种的默认类型（code, label, sort_order）
DEFAULT_TYPES: tuple[tuple[str, str, int], ...] = (
    ("customer_service", "客服对话", 10),
    ("sales", "销售", 20),
    ("support", "支持", 30),
    ("other", "其他", 90),
)


def _normalize_code(raw: str | None) -> str:
    """校验/生成类型标识（统一小写）。"""
    code = (raw or "").strip().lower()
    if not code:
        return f"t_{uuid.uuid4().hex[:8]}"
    if not CODE_PATTERN.match(code):
        raise DataSourceTypeInvalidError("类型标识只能包含小写字母、数字和下划线，且以字母开头（2-50 位）")
    return code


async def ensure_user_defaults(session: AsyncSession, user_id: uuid.UUID) -> None:
    """为用户播种默认类型（幂等；并发安全靠唯一索引 + ON CONFLICT DO NOTHING）。"""
    exists = await session.scalar(
        select(DataSourceType.id).where(DataSourceType.owner_user_id == user_id).limit(1)
    )
    if exists is not None:
        return
    stmt = (
        pg_insert(DataSourceType)
        .values(
            [
                {
                    "owner_user_id": user_id,
                    "code": code,
                    "label": label,
                    "sort_order": sort_order,
                    "is_system": True,
                    "is_active": True,
                }
                for code, label, sort_order in DEFAULT_TYPES
            ]
        )
        .on_conflict_do_nothing(index_elements=["owner_user_id", "code"])
    )
    await session.execute(stmt)
    await session.flush()


async def _usage_count(session: AsyncSession, user_id: uuid.UUID, code: str) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(DataSource)
            .where(
                DataSource.user_id == user_id,
                DataSource.type == code,
                DataSource.deleted_at.is_(None),
            )
        )
        or 0
    )


async def _active_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(DataSourceType)
            .where(
                DataSourceType.owner_user_id == user_id,
                DataSourceType.is_active.is_(True),
            )
        )
        or 0
    )


async def list_types(
    session: AsyncSession, *, user_id: uuid.UUID, include_inactive: bool = False
) -> list[tuple[DataSourceType, int]]:
    """返回当前用户的 [(类型, 该用户使用中的数据源数量)]，按 sort_order 升序。"""
    await ensure_user_defaults(session, user_id)

    stmt = (
        select(DataSourceType, func.count(DataSource.id))
        .outerjoin(
            DataSource,
            and_(
                DataSource.type == DataSourceType.code,
                DataSource.user_id == user_id,
                DataSource.deleted_at.is_(None),
            ),
        )
        .where(DataSourceType.owner_user_id == user_id)
        .group_by(DataSourceType.id)
        .order_by(DataSourceType.sort_order.asc(), DataSourceType.created_at.asc())
    )
    if not include_inactive:
        stmt = stmt.where(DataSourceType.is_active.is_(True))
    rows = (await session.execute(stmt)).all()
    return [(row[0], int(row[1])) for row in rows]


async def get(session: AsyncSession, user_id: uuid.UUID, type_id: uuid.UUID) -> DataSourceType:
    """按 id 取当前用户的类型；他人类型一律 404。"""
    row = await session.scalar(
        select(DataSourceType).where(
            DataSourceType.id == type_id,
            DataSourceType.owner_user_id == user_id,
        )
    )
    if row is None:
        raise DataSourceTypeNotFoundError(details={"type_id": str(type_id)})
    return row


async def ensure_usable(session: AsyncSession, user_id: uuid.UUID, code: str) -> DataSourceType:
    """校验类型归属当前用户且启用；未知/停用 → 400。"""
    await ensure_user_defaults(session, user_id)
    row = await session.scalar(
        select(DataSourceType).where(
            DataSourceType.owner_user_id == user_id,
            DataSourceType.code == code,
        )
    )
    if row is None:
        raise DataSourceTypeInvalidError(f"未知的数据源类型：{code}")
    if not row.is_active:
        raise DataSourceTypeInvalidError(f"数据源类型已停用：{row.label}")
    return row


async def _next_sort_order(session: AsyncSession, user_id: uuid.UUID) -> int:
    current = await session.scalar(
        select(func.max(DataSourceType.sort_order)).where(DataSourceType.owner_user_id == user_id)
    )
    return int(current or 0) + 10


async def create(
    session: AsyncSession, user_id: uuid.UUID, data: DataSourceTypeCreate
) -> DataSourceType:
    await ensure_user_defaults(session, user_id)
    code = _normalize_code(data.code)
    exists = await session.scalar(
        select(DataSourceType.id).where(
            DataSourceType.owner_user_id == user_id,
            DataSourceType.code == code,
        )
    )
    if exists is not None:
        raise DataSourceTypeInvalidError(f"类型标识已存在：{code}")

    row = DataSourceType(
        owner_user_id=user_id,
        code=code,
        label=data.label.strip(),
        description=(data.description or "").strip() or None,
        sort_order=(
            data.sort_order
            if data.sort_order is not None
            else await _next_sort_order(session, user_id)
        ),
        is_system=False,
        is_active=True,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def update(
    session: AsyncSession, user_id: uuid.UUID, type_id: uuid.UUID, data: DataSourceTypeUpdate
) -> DataSourceType:
    row = await get(session, user_id, type_id)
    payload = data.model_dump(exclude_unset=True)

    if payload.get("label") is not None:
        row.label = payload["label"].strip()
    if "description" in payload:
        row.description = (payload["description"] or "").strip() or None
    if payload.get("sort_order") is not None:
        row.sort_order = int(payload["sort_order"])
    if payload.get("is_active") is not None:
        next_active = bool(payload["is_active"])
        if row.is_active and not next_active and await _active_count(session, user_id) <= 1:
            raise DataSourceTypeInvalidError("至少保留一个启用的类型")
        row.is_active = next_active

    await session.flush()
    await session.refresh(row)
    return row


async def delete(session: AsyncSession, user_id: uuid.UUID, type_id: uuid.UUID) -> None:
    row = await get(session, user_id, type_id)
    if row.is_system:
        raise DataSourceTypeInvalidError("默认类型不可删除，可改为停用")
    usage = await _usage_count(session, user_id, row.code)
    if usage:
        raise DataSourceTypeInUseError(
            f"该类型仍被 {usage} 个数据源使用，无法删除",
            details={"usage_count": usage},
        )
    if row.is_active and await _active_count(session, user_id) <= 1:
        raise DataSourceTypeInvalidError("至少保留一个启用的类型")
    await session.delete(row)
    await session.flush()
