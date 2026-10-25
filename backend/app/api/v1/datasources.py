"""数据源接口（API 设计 §5、§6）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.pagination import PaginationParams
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import FileFormatInvalidError, FileTooLargeError
from app.models import RawData, User
from app.schemas.base import Page
from app.schemas.cleaned_data import CleanedDataDetail, CleanedDataItem
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceDeleteResponse,
    DataSourceItem,
    DataSourceResponse,
    DataSourceUpdate,
    DataSourceUpdateResponse,
)
from app.schemas.processing import (
    CleanRequest,
    CleanResponse,
    FileInfo,
    UploadResponse,
)
from app.services import cleaning_service, datasource_service, parsers, storage_service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")

# raw_data.raw_content.text 入库上限（更大文件由对象存储承载，清洗 Agent 走存储读取）
MAX_RAW_TEXT_CHARS = 200_000
# 粗估：每条原始记录约 0.2 秒
SECONDS_PER_RECORD = 0.2


@router.post(
    "",
    status_code=201,
    response_model=DataSourceResponse,
    response_model_by_alias=False,
    summary="创建数据源",
)
async def create_datasource(
    payload: DataSourceCreate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    datasource = await datasource_service.create(session, user=user, data=payload)
    return DataSourceResponse.model_validate(datasource)


@router.get(
    "",
    response_model=Page[DataSourceItem],
    response_model_by_alias=False,
    summary="数据源列表（分页/过滤/排序）",
)
async def list_datasources(
    params: PaginationParams = Depends(),
    status: str | None = Query(default=None, description="按状态过滤"),
    type: str | None = Query(default=None, description="按类型过滤"),  # noqa: A002
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[DataSourceItem]:
    rows, pagination = await datasource_service.list_datasources(
        session,
        user=user,
        params=params,
        status=status,
        data_source_type=type,
    )
    return Page[DataSourceItem](
        items=[DataSourceItem.model_validate(item) for item in rows],
        pagination=pagination,
    )


@router.get(
    "/{datasource_id}",
    response_model=DataSourceResponse,
    response_model_by_alias=False,
    summary="数据源详情",
)
async def get_datasource(
    datasource_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    datasource = await datasource_service.get(session, user=user, datasource_id=datasource_id)
    return DataSourceResponse.model_validate(datasource)


@router.patch(
    "/{datasource_id}",
    response_model=DataSourceUpdateResponse,
    response_model_by_alias=False,
    summary="更新数据源（局部更新）",
)
async def update_datasource(
    datasource_id: uuid.UUID,
    payload: DataSourceUpdate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> DataSourceUpdateResponse:
    datasource = await datasource_service.update(
        session, user=user, datasource_id=datasource_id, data=payload
    )
    return DataSourceUpdateResponse(
        id=datasource.id,
        name=datasource.name,
        description=datasource.description,
        updated_at=datasource.updated_at,
    )


@router.delete(
    "/{datasource_id}",
    response_model=DataSourceDeleteResponse,
    response_model_by_alias=False,
    summary="删除数据源（默认软删，force=true 物理删除）",
)
async def delete_datasource(
    datasource_id: uuid.UUID,
    force: bool = Query(default=False, description="是否物理删除并级联清理关联数据"),
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> DataSourceDeleteResponse:
    message, deleted_records = await datasource_service.delete(
        session, user=user, datasource_id=datasource_id, force=force
    )
    return DataSourceDeleteResponse(message=message, deleted_records=deleted_records)


def _allowed_extensions() -> set[str]:
    return {
        item.strip().lower().lstrip(".")
        for item in settings.ALLOWED_UPLOAD_EXTENSIONS.split(",")
        if item.strip()
    }


@router.post(
    "/{datasource_id}/upload",
    status_code=202,
    response_model=UploadResponse,
    response_model_by_alias=False,
    summary="上传数据文件并自动入队清洗（202 + task_id）",
)
async def upload_file(
    datasource_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> UploadResponse:
    datasource = await datasource_service.get(session, user=user, datasource_id=datasource_id)

    filename = file.filename or "upload.bin"
    content = await file.read()

    # 413：超过大小上限
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise FileTooLargeError(
            details={
                "filename": filename,
                "size": len(content),
                "max_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            }
        )

    # 415：扩展名不在白名单
    extension = Path(filename).suffix.lower().lstrip(".")
    allowed = _allowed_extensions()
    if extension not in allowed:
        raise FileFormatInvalidError(details={"filename": filename, "allowed": sorted(allowed)})

    # 解析失败同样归为 415（FILE_FORMAT_INVALID）
    try:
        parsed = parsers.parse_upload(content, filename)
    except parsers.ParseError as exc:
        raise FileFormatInvalidError(str(exc), details={"filename": filename}) from exc

    stored = storage_service.save_upload(
        content,
        datasource_id=datasource.id,
        filename=filename,
        content_type=file.content_type,
    )

    raw_data = RawData(
        datasource_id=datasource.id,
        raw_content={
            "text": parsed.raw_text[:MAX_RAW_TEXT_CHARS],
            "format": parsed.format,
            "encoding": parsed.encoding,
            "record_count": parsed.record_count,
            "truncated": len(parsed.raw_text) > MAX_RAW_TEXT_CHARS,
        },
        file_info={
            "filename": filename,
            "size": len(content),
            "mime_type": file.content_type,
            "upload_url": stored.url,
            "storage_backend": stored.backend,
        },
        status="pending",
    )
    session.add(raw_data)
    await session.flush()
    await session.refresh(raw_data)

    datasource.workflow_status = "data_uploaded"

    task = await cleaning_service.create_clean_task(
        session,
        user=user,
        datasource_id=datasource.id,
        task_name="上传后清洗",
        params={
            "raw_data_id": str(raw_data.id),
            "config": {"remove_duplicates": True, "normalize_text": True},
        },
    )
    task.celery_task_id = cleaning_service.enqueue_clean(task)
    await session.flush()
    await session.refresh(task)

    return UploadResponse(
        task_id=task.id,
        status=task.status,
        file_info=FileInfo(
            filename=filename,
            size=len(content),
            mime_type=file.content_type,
            upload_url=stored.url,
            storage_backend=stored.backend,
        ),
    )


@router.post(
    "/{datasource_id}/clean",
    status_code=202,
    response_model=CleanResponse,
    response_model_by_alias=False,
    summary="触发数据清洗（202 + task_id；同数据源同类任务在跑返回 409）",
)
async def clean_datasource(
    datasource_id: uuid.UUID,
    payload: CleanRequest | None = None,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> CleanResponse:
    datasource = await datasource_service.get(session, user=user, datasource_id=datasource_id)
    request = payload or CleanRequest()

    await cleaning_service.ensure_no_running_task(session, datasource_id=datasource.id)

    pending = await cleaning_service.count_pending_records(session, datasource.id)
    record_count = len(request.data_ids) or pending
    estimated_duration = max(5.0, round(record_count * SECONDS_PER_RECORD, 1))
    if not record_count:
        estimated_duration = 5.0

    task = await cleaning_service.create_clean_task(
        session,
        user=user,
        datasource_id=datasource.id,
        task_name="数据清洗",
        params={
            "data_ids": [str(item) for item in request.data_ids],
            "config": request.config.model_dump(),
        },
    )
    task.celery_task_id = cleaning_service.enqueue_clean(task)
    await session.flush()
    await session.refresh(task)

    return CleanResponse(
        task_id=task.id,
        estimated_duration=estimated_duration,
        message="Cleaning task queued",
    )


@router.get(
    "/{datasource_id}/cleaned-data",
    response_model=Page[CleanedDataItem],
    response_model_by_alias=False,
    summary="清洗结果列表（分页/质量分/问题/日期过滤）",
)
async def list_cleaned_data(
    datasource_id: uuid.UUID,
    params: PaginationParams = Depends(),
    quality_score_min: float | None = Query(default=None, ge=0, le=100),
    quality_score_max: float | None = Query(default=None, ge=0, le=100),
    has_issues: bool | None = Query(default=None, description="是否只看有问题/无问题数据"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[CleanedDataItem]:
    rows, pagination = await cleaning_service.list_cleaned_data(
        session,
        user=user,
        datasource_id=datasource_id,
        params=params,
        quality_score_min=quality_score_min,
        quality_score_max=quality_score_max,
        has_issues=has_issues,
        date_from=date_from,
        date_to=date_to,
    )
    return Page[CleanedDataItem](
        items=[CleanedDataItem.model_validate(item) for item in rows],
        pagination=pagination,
    )


@router.get(
    "/{datasource_id}/cleaned-data/{data_id}",
    response_model=CleanedDataDetail,
    response_model_by_alias=False,
    summary="清洗结果详情",
)
async def get_cleaned_data(
    datasource_id: uuid.UUID,
    data_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> CleanedDataDetail:
    item = await cleaning_service.get_cleaned_data(
        session, user=user, datasource_id=datasource_id, data_id=data_id
    )
    return CleanedDataDetail.model_validate(item)


__all__ = ["router"]
