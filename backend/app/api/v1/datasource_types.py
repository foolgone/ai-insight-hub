"""数据源类型字典接口（增删改查）。

- 读：登录用户均可（新建/编辑数据源时的下拉需要）；
- 写：仅 admin（全局字典，影响所有用户）；
- ``code`` 创建后不可改；内置类型不可删；仍被引用不可删（409）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import DataSourceType, User
from app.schemas.datasource_type import (
    DataSourceTypeCreate,
    DataSourceTypeItem,
    DataSourceTypeList,
    DataSourceTypeUpdate,
)
from app.services import datasource_type_service

router = APIRouter()


def _to_item(row: DataSourceType, usage_count: int) -> DataSourceTypeItem:
    return DataSourceTypeItem(
        id=row.id,
        code=row.code,
        label=row.label,
        description=row.description,
        sort_order=row.sort_order,
        is_system=row.is_system,
        is_active=row.is_active,
        usage_count=usage_count,
        created_at=row.created_at,
    )


@router.get(
    "",
    response_model=DataSourceTypeList,
    response_model_by_alias=False,
    summary="数据源类型列表（按 sort_order 升序，带使用量）",
)
async def list_datasource_types(
    include_inactive: bool = Query(default=False, description="是否包含已停用类型"),
    _user: User = Depends(require_roles("admin", "user", "viewer")),
    session: AsyncSession = Depends(get_db),
) -> DataSourceTypeList:
    rows = await datasource_type_service.list_types(
        session, include_inactive=include_inactive
    )
    return DataSourceTypeList(items=[_to_item(row, usage) for row, usage in rows])


@router.post(
    "",
    response_model=DataSourceTypeItem,
    response_model_by_alias=False,
    status_code=status.HTTP_201_CREATED,
    summary="新增数据源类型（admin）",
)
async def create_datasource_type(
    payload: DataSourceTypeCreate,
    _user: User = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_db),
) -> DataSourceTypeItem:
    row = await datasource_type_service.create(session, payload)
    return _to_item(row, 0)


@router.patch(
    "/{type_id}",
    response_model=DataSourceTypeItem,
    response_model_by_alias=False,
    summary="修改类型名称/描述/排序/启停（admin；code 不可改）",
)
async def update_datasource_type(
    type_id: uuid.UUID,
    payload: DataSourceTypeUpdate,
    _user: User = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_db),
) -> DataSourceTypeItem:
    row = await datasource_type_service.update(session, type_id, payload)
    rows = await datasource_type_service.list_types(session, include_inactive=True)
    usage = next((count for item, count in rows if item.id == row.id), 0)
    return _to_item(row, usage)


@router.delete(
    "/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除数据源类型（admin；内置类型与使用中类型不可删）",
)
async def delete_datasource_type(
    type_id: uuid.UUID,
    _user: User = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await datasource_type_service.delete(session, type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
