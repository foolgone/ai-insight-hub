"""文件处理 Schemas（API 设计 §6）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class FileInfo(BaseSchema):
    filename: str
    size: int
    mime_type: str | None = None
    storage_backend: str | None = None
    # 刻意不返回 upload_url：内部对象地址（http://minio:9000/<bucket>/<object>）
    # 对前端无用，且会暴露内网主机名与桶结构。需要下载走 API 鉴权代理。


class UploadResponse(BaseSchema):
    """上传响应（API §6.1：202 + task_id + file_info）。"""

    task_id: uuid.UUID
    status: str
    file_info: FileInfo


class CleaningConfig(BaseSchema):
    remove_duplicates: bool = True
    normalize_text: bool = True


class CleanRequest(BaseSchema):
    data_ids: list[uuid.UUID] = Field(default_factory=list)
    config: CleaningConfig = Field(default_factory=CleaningConfig)


class CleanResponse(BaseSchema):
    """清洗入队响应（API §6.2：202 + task_id + 预计耗时）。"""

    task_id: uuid.UUID
    estimated_duration: float
    message: str


class RawDataItem(BaseSchema):
    """一个上传文件的「转写 / 切分」状态（转写与拆分拆开后的列表）。"""

    id: uuid.UUID
    filename: str | None = None
    size: int | None = None
    format: str | None = None
    duration: float | None = None
    channels: int | None = None
    channel_mode: str | None = None
    asr_status: str = "pending"
    # pending（未切分）/ done（已切分）/ failed（切分失败）
    structure_status: str = "pending"
    structure_kind: str | None = None
    qa_count: int = 0
    partial: bool = False
    error: str | None = None
    status: str = "pending"
    created_at: datetime | None = None
    processed_at: datetime | None = None


class RawDataListResponse(BaseSchema):
    items: list[RawDataItem]


class StructureResponse(BaseSchema):
    task_id: uuid.UUID
    message: str


__all__ = [
    "CleanRequest",
    "CleanResponse",
    "CleaningConfig",
    "FileInfo",
    "RawDataItem",
    "RawDataListResponse",
    "StructureResponse",
    "UploadResponse",
]
