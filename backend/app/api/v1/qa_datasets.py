"""RAG 评测数据集 API（Phase 1）。

权限：
- 读（GET）：admin/user/viewer；
- 写（POST/PATCH/DELETE）：admin/user；
- 归属：admin 全通，其余仅本人（``assert_owner``）。

语义：
- 版本发布后**不可变**：任何写操作返回 409（``QA_DATASET_IMMUTABLE``）；
- 导入先全量校验再写库：失败返回 400，``details.errors`` 带 1-based 行号。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import pagination_params, require_roles
from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.models import QaDatasetItem, User
from app.schemas.base import Page
from app.schemas.qa_dataset import (
    ItemSplit,
    QaDatasetCreate,
    QaDatasetDetail,
    QaDatasetImportRequest,
    QaDatasetImportResult,
    QaDatasetItemRead,
    QaDatasetItemUpdate,
    QaDatasetRead,
    QaDatasetStats,
    QaDatasetUpdate,
    QaDatasetVersionCreate,
    QaDatasetVersionRead,
)
from app.services import qa_dataset_service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")


def _item_to_read(item: QaDatasetItem) -> QaDatasetItemRead:
    """ORM 条目 → 响应（``item_metadata`` 属性映射为 ``metadata`` 字段）。"""
    return QaDatasetItemRead(
        id=item.id,
        item_key=item.item_key,
        query=item.query,
        gold_answer=item.gold_answer,
        gold_evidence=list(item.gold_evidence or []),
        category=item.category,
        difficulty=item.difficulty,
        source=item.source,
        split=item.split,
        metadata=dict(item.item_metadata or {}),
        created_at=item.created_at,
    )


# --------------------------------------------------------------------------- 数据集


@router.post(
    "",
    response_model=QaDatasetRead,
    response_model_by_alias=False,
    status_code=status.HTTP_201_CREATED,
    summary="创建数据集",
)
async def create_dataset(
    payload: QaDatasetCreate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetRead:
    dataset = await qa_dataset_service.create_dataset(session, user=user, payload=payload)
    return QaDatasetRead.model_validate(dataset, from_attributes=True)


@router.get(
    "",
    response_model=Page[QaDatasetRead],
    response_model_by_alias=False,
    summary="数据集列表（分页 + 名称关键词）",
)
async def list_datasets(
    keyword: str | None = Query(default=None, max_length=100),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[QaDatasetRead]:
    rows, pagination = await qa_dataset_service.list_datasets(
        session, user=user, keyword=keyword, params=params
    )
    return Page[QaDatasetRead](
        items=[QaDatasetRead.model_validate(row, from_attributes=True) for row in rows],
        pagination=pagination,
    )


@router.get(
    "/{dataset_id}",
    response_model=QaDatasetDetail,
    response_model_by_alias=False,
    summary="数据集详情（含版本列表）",
)
async def get_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetDetail:
    dataset, versions = await qa_dataset_service.get_dataset_detail(
        session, user=user, dataset_id=dataset_id
    )
    detail = QaDatasetDetail.model_validate(dataset, from_attributes=True)
    detail.versions = [
        QaDatasetVersionRead.model_validate(row, from_attributes=True) for row in versions
    ]
    return detail


@router.patch(
    "/{dataset_id}",
    response_model=QaDatasetRead,
    response_model_by_alias=False,
    summary="更新数据集元信息（不影响已发布版本）",
)
async def update_dataset(
    dataset_id: uuid.UUID,
    payload: QaDatasetUpdate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetRead:
    dataset = await qa_dataset_service.update_dataset(
        session, user=user, dataset_id=dataset_id, payload=payload
    )
    return QaDatasetRead.model_validate(dataset, from_attributes=True)


# --------------------------------------------------------------------------- 版本


@router.post(
    "/{dataset_id}/versions",
    response_model=QaDatasetVersionRead,
    response_model_by_alias=False,
    status_code=status.HTTP_201_CREATED,
    summary="创建草稿版本（可从一个已有版本复制）",
)
async def create_version(
    dataset_id: uuid.UUID,
    payload: QaDatasetVersionCreate | None = None,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetVersionRead:
    request = payload or QaDatasetVersionCreate()
    version = await qa_dataset_service.create_version(
        session,
        user=user,
        dataset_id=dataset_id,
        note=request.note,
        from_version_id=request.from_version_id,
    )
    return QaDatasetVersionRead.model_validate(version, from_attributes=True)


@router.get(
    "/{dataset_id}/versions",
    response_model=list[QaDatasetVersionRead],
    response_model_by_alias=False,
    summary="版本列表（按版本号倒序）",
)
async def list_versions(
    dataset_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> list[QaDatasetVersionRead]:
    _, versions = await qa_dataset_service.get_dataset_detail(
        session, user=user, dataset_id=dataset_id
    )
    return [QaDatasetVersionRead.model_validate(row, from_attributes=True) for row in versions]


@router.post(
    "/{dataset_id}/versions/{version_id}/import",
    response_model=QaDatasetImportResult,
    response_model_by_alias=False,
    summary="导入条目（全量校验，失败整批回滚）",
)
async def import_items(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: QaDatasetImportRequest,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetImportResult:
    imported, total = await qa_dataset_service.import_items(
        session,
        user=user,
        dataset_id=dataset_id,
        version_id=version_id,
        raw_items=payload.items,
    )
    return QaDatasetImportResult(imported=imported, version_item_count=total)


@router.post(
    "/{dataset_id}/versions/{version_id}/publish",
    response_model=QaDatasetVersionRead,
    response_model_by_alias=False,
    summary="发布版本（发布后不可变）",
)
async def publish_version(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetVersionRead:
    version = await qa_dataset_service.publish_version(
        session, user=user, dataset_id=dataset_id, version_id=version_id
    )
    return QaDatasetVersionRead.model_validate(version, from_attributes=True)


# --------------------------------------------------------------------------- 条目


@router.get(
    "/{dataset_id}/versions/{version_id}/items",
    response_model=Page[QaDatasetItemRead],
    response_model_by_alias=False,
    summary="条目列表（split / category / 关键词）",
)
async def list_items(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    split: ItemSplit | None = Query(default=None),
    category: str | None = Query(default=None, max_length=100),
    keyword: str | None = Query(default=None, max_length=200),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[QaDatasetItemRead]:
    rows, pagination = await qa_dataset_service.list_items(
        session,
        user=user,
        dataset_id=dataset_id,
        version_id=version_id,
        split=split,
        category=category,
        keyword=keyword,
        params=params,
    )
    return Page[QaDatasetItemRead](
        items=[_item_to_read(row) for row in rows],
        pagination=pagination,
    )


@router.get(
    "/{dataset_id}/versions/{version_id}/items/{item_id}",
    response_model=QaDatasetItemRead,
    response_model_by_alias=False,
    summary="条目详情",
)
async def get_item(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetItemRead:
    item = await qa_dataset_service.get_item(
        session,
        user=user,
        dataset_id=dataset_id,
        version_id=version_id,
        item_id=item_id,
    )
    return _item_to_read(item)


@router.patch(
    "/{dataset_id}/versions/{version_id}/items/{item_id}",
    response_model=QaDatasetItemRead,
    response_model_by_alias=False,
    summary="更新条目（仅 draft 版本）",
)
async def update_item(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: QaDatasetItemUpdate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetItemRead:
    item = await qa_dataset_service.update_item(
        session,
        user=user,
        dataset_id=dataset_id,
        version_id=version_id,
        item_id=item_id,
        payload=payload,
    )
    return _item_to_read(item)


@router.delete(
    "/{dataset_id}/versions/{version_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除条目（仅 draft 版本）",
)
async def delete_item(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await qa_dataset_service.delete_item(
        session,
        user=user,
        dataset_id=dataset_id,
        version_id=version_id,
        item_id=item_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- 统计


@router.get(
    "/{dataset_id}/stats",
    response_model=QaDatasetStats,
    response_model_by_alias=False,
    summary="版本统计（条目数 / split / 分类 / 证据覆盖率）",
)
async def dataset_stats(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID = Query(...),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QaDatasetStats:
    return await qa_dataset_service.stats(
        session, user=user, dataset_id=dataset_id, version_id=version_id
    )
