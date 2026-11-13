"""数据源接口（API 设计 §5、§6）。"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition import enqueue
from app.api.deps import require_llm_credential, require_roles
from app.api.deps import pagination_params
from app.core.pagination import PaginationParams
from app.repositories import raw_data as raw_data_repo
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    AIInsightHubException,
    AsrCredentialInvalidError,
    AsrCredentialNotConfiguredError,
    FileFormatInvalidError,
    FileTooLargeError,
)
from app.core.errors import FrameworkErrorCode
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
    RawDataItem,
    RawDataListResponse,
    StructureResponse,
    UploadResponse,
)
from app.services import (
    cleaning_service,
    datasource_service,
    parsers,
    storage_service,
    structure_task_service,
)
from app.services.credential_service import PROVIDER_ASR, credential_service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")

# raw_data.raw_content.text 入库上限（更大文件由对象存储承载，清洗 Agent 走存储读取）
MAX_RAW_TEXT_CHARS = 200_000
# 粗估：每条原始记录约 0.2 秒
SECONDS_PER_RECORD = 0.2

# 流式落盘的分块大小（1MB）：避免 100MB 级音视频整块读进内存
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _spool_upload(file: UploadFile, max_bytes: int) -> tuple[Path, int]:
    """把上传流写到临时文件，边写边校验大小；返回 ``(临时路径, 字节数)``。"""
    fd, path_str = tempfile.mkstemp(prefix="aiih-upload-")
    path = Path(path_str)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError(
                        details={
                            "filename": file.filename or "upload.bin",
                            "size": size,
                            "max_size_mb": settings.MAX_UPLOAD_SIZE_MB,
                        }
                    )
                out.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, size


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
    params: PaginationParams = Depends(pagination_params),
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


def _media_extensions() -> set[str]:
    return {
        item.strip().lower().lstrip(".")
        for item in settings.MEDIA_UPLOAD_EXTENSIONS.split(",")
        if item.strip()
    }


@router.post(
    "/{datasource_id}/upload",
    status_code=202,
    response_model=UploadResponse,
    response_model_by_alias=False,
    summary="上传数据文件并自动入队清洗（202 + task_id）",
    dependencies=[Depends(require_llm_credential)],
)
async def upload_file(
    datasource_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> UploadResponse:
    datasource = await datasource_service.get(session, user=user, datasource_id=datasource_id)

    filename = file.filename or "upload.bin"
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # 413：Content-Length 已声明超限时直接拒绝（不必先落盘）
    if file.size is not None and file.size > max_bytes:
        raise FileTooLargeError(
            details={
                "filename": filename,
                "size": file.size,
                "max_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            }
        )

    # 415：扩展名不在白名单
    extension = Path(filename).suffix.lower().lstrip(".")
    allowed = _allowed_extensions()
    media_exts = _media_extensions()
    is_media = extension in media_exts
    if extension not in allowed and not is_media:
        raise FileFormatInvalidError(
            details={"filename": filename, "allowed": sorted(allowed | media_exts)}
        )

    if is_media:
        # 音视频需要用户自己的 ASR 配置（BYOK）；功能关闭时仍按 415 拒绝
        if not settings.ASR_ENABLED:
            raise FileFormatInvalidError(
                "音视频上传功能未开启",
                details={"filename": filename, "reason": "asr_disabled"},
            )
        asr_row = await credential_service.get_credential(session, user.id, PROVIDER_ASR)
        if asr_row is None:
            raise AsrCredentialNotConfiguredError()
        if asr_row.status != "active":
            raise AsrCredentialInvalidError()

    # 流式落盘：大文件（音视频 100MB 级）不再整块读进内存
    tmp_path, size = await _spool_upload(file, max_bytes)

    try:
        # 文本类解析失败归为 415；媒体不解析，交由 clean 任务转写
        parsed = None
        if not is_media:
            try:
                parsed = parsers.parse_upload(tmp_path.read_bytes(), filename)
            except parsers.ParseError as exc:
                raise FileFormatInvalidError(str(exc), details={"filename": filename}) from exc

        stored = storage_service.save_upload_from_path(
            tmp_path,
            datasource_id=datasource.id,
            filename=filename,
            content_type=file.content_type,
            size=size,
        )

        if is_media:
            raw_content: dict[str, Any] = {
                "format": "media",
                "media": {
                    "filename": filename,
                    "mime_type": file.content_type,
                    "size": size,
                },
                "asr": {"status": "pending"},
            }
        else:
            # 非媒体分支一定已在上面解析成功（失败会抛 415）
            assert parsed is not None
            raw_content = {
                "text": parsed.raw_text[:MAX_RAW_TEXT_CHARS],
                "format": parsed.format,
                "encoding": parsed.encoding,
                "record_count": parsed.record_count,
                "truncated": len(parsed.raw_text) > MAX_RAW_TEXT_CHARS,
            }

        raw_data = RawData(
            datasource_id=datasource.id,
            raw_content=raw_content,
            file_info={
                "filename": filename,
                "size": size,
                "mime_type": file.content_type,
                "object_name": stored.object_name,
                "storage_backend": stored.backend,
            },
            status="pending",
        )
        await raw_data_repo.add(session, raw_data)
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
        task.celery_task_id = enqueue.enqueue_clean(str(task.id))
        await session.flush()
        await session.refresh(task)

        return UploadResponse(
            task_id=task.id,
            status=task.status,
            file_info=FileInfo(
                filename=filename,
                size=size,
                mime_type=file.content_type,
                storage_backend=stored.backend,
            ),
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post(
    "/{datasource_id}/clean",
    status_code=202,
    response_model=CleanResponse,
    response_model_by_alias=False,
    summary="触发数据清洗（202 + task_id；同数据源同类任务在跑返回 409）",
    dependencies=[Depends(require_llm_credential)],
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
        # 以前这里只把预估时长兜成 5 秒，结果建了一个注定失败的任务：
        # worker 里才抛 "no raw data to clean"，前端看到一个 5% 失败的任务。
        raise AIInsightHubException(
            "该数据源没有待清洗文件（可选：重新上传文件，或对失败任务点「重试」）",
            code=FrameworkErrorCode.BAD_REQUEST,
            status_code=400,
            details={"datasource_id": str(datasource.id), "pending_records": 0},
        )

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
    task.celery_task_id = enqueue.enqueue_clean(str(task.id))
    await session.flush()
    await session.refresh(task)

    return CleanResponse(
        task_id=task.id,
        estimated_duration=estimated_duration,
        message="Cleaning task queued",
    )


@router.get(
    "/{datasource_id}/raw-data",
    response_model=RawDataListResponse,
    response_model_by_alias=False,
    summary="上传文件列表（转写 / 切分状态）",
)
async def list_raw_data(
    datasource_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RawDataListResponse:
    datasource = await datasource_service.get(session, user=user, datasource_id=datasource_id)
    rows = await raw_data_repo.list_for_datasource(session, datasource.id)
    items: list[RawDataItem] = []
    for raw in reversed(rows):  # 最新上传在前
        content = raw.raw_content or {}
        media = content.get("media") or {}
        file_info = raw.file_info or {}
        state = structure_task_service.structure_state(raw)
        items.append(
            RawDataItem(
                id=raw.id,
                filename=file_info.get("filename"),
                size=file_info.get("size"),
                format=content.get("format"),
                duration=media.get("duration"),
                channels=media.get("channels"),
                channel_mode=media.get("channel_mode"),
                status=raw.status,
                created_at=raw.created_at,
                processed_at=raw.processed_at,
                **state,
            )
        )
    return RawDataListResponse(items=items)


@router.post(
    "/{datasource_id}/raw-data/{raw_id}/structure",
    status_code=202,
    response_model=StructureResponse,
    response_model_by_alias=False,
    summary="对已转写文件重新切分（202 + task_id）",
    dependencies=[Depends(require_llm_credential)],
)
async def structure_raw_data(
    datasource_id: uuid.UUID,
    raw_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> StructureResponse:
    datasource = await datasource_service.get(session, user=user, datasource_id=datasource_id)
    raw = await raw_data_repo.get(session, raw_id)
    if raw is None or raw.datasource_id != datasource.id:
        raise AIInsightHubException(
            "Raw data not found", code=FrameworkErrorCode.HTTP_ERROR, status_code=404
        )
    task = await structure_task_service.create_structure_task(session, user_id=user.id, raw=raw)
    task.celery_task_id = enqueue.enqueue_structure(str(task.id))
    await session.flush()
    await session.refresh(task)
    return StructureResponse(task_id=task.id, message="Structure task queued")


@router.get(
    "/{datasource_id}/cleaned-data",
    response_model=Page[CleanedDataItem],
    response_model_by_alias=False,
    summary="清洗结果列表（分页/质量分/问题/日期过滤）",
)
async def list_cleaned_data(
    datasource_id: uuid.UUID,
    params: PaginationParams = Depends(pagination_params),
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
