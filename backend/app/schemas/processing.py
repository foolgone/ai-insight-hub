"""文件处理 Schemas（API 设计 §6）。"""
from __future__ import annotations

import uuid

from pydantic import Field

from app.schemas.base import BaseSchema


class FileInfo(BaseSchema):
    filename: str
    size: int
    mime_type: str | None = None
    upload_url: str | None = None
    storage_backend: str | None = None


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


__all__ = [
    "CleanRequest",
    "CleanResponse",
    "CleaningConfig",
    "FileInfo",
    "UploadResponse",
]
