"""数据源类型字典接口（按用户隔离的增删改查）。

- 所有端点只作用于**当前登录用户自己的**类型（不接收他人 ``user_id``，越权 404）；
- 读：admin / user / viewer 均可（新建/编辑数据源时的下拉需要）；
- 写：admin / user（类型是用户自己的配置，viewer 只读）；
- ``code`` 创建后不可改；默认类型不可删；仍被引用不可删（409）；
- 不允许删/停最后一个启用类型。
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
    summary="当前用户的数据源类型列表（首次访问自动播种默认类型）",
)
async def list_datasource_types(
    include_inactive: bool = Query(default=False, description="是否包含已停用类型"),
    user: User = Depends(require_roles("admin", "user", "viewer")),
    session: AsyncSession = Depends(get_db),
) -> DataSourceTypeList:
    rows = await datasource_type_service.list_types(
        session, user_id=user.id, include_inactive=include_inactive
    )
    return DataSourceTypeList(items=[_to_item(row, usage) for row, usage in rows])


@router.post(
    "",
    response_model=DataSourceTypeItem,
    response_model_by_alias=False,
    status_code=status.HTTP_201_CREATED,
    summary="新增自己的数据源类型",
)
async def create_datasource_type(
    payload: DataSourceTypeCreate,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> DataSourceTypeItem:
    row = await datasource_type_service.create(session, user.id, payload)
    return _to_item(row, 0)


@router.patch(
    "/{type_id}",
    response_model=DataSourceTypeItem,
    response_model_by_alias=False,
    summary="修改自己的类型名称/描述/排序/启停（code 不可改）",
)
async def update_datasource_type(
    type_id: uuid.UUID,
    payload: DataSourceTypeUpdate,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> DataSourceTypeItem:
    row = await datasource_type_service.update(session, user.id, type_id, payload)
    rows = await datasource_type_service.list_types(
        session, user_id=user.id, include_inactive=True
    )
    usage = next((count for item, count in rows if item.id == row.id), 0)
    return _to_item(row, usage)


@router.delete(
    "/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自己的类型（默认类型与使用中类型不可删）",
)
async def delete_datasource_type(
    type_id: uuid.UUID,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await datasource_type_service.delete(session, user.id, type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
