"""对象存储服务（B-304）。

- 默认 MinIO（S3 兼容）；``STORAGE_BACKEND=auto`` 时 MinIO 不可用自动回退本地文件系统
  （本地 VM 上 MinIO 未启动，属预期路径）；
- 对象命名：``{datasource_id}/{uuid}_{filename}``（filename 取 basename，防目录穿越）；
- 返回 ``StoredFile``（object_name / url / backend / size），由调用方写入 ``raw_data.file_info``。
"""
from __future__ import annotations

import uuid as uuid_module
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from loguru import logger

from app.core.config import settings


@dataclass(frozen=True)
class StoredFile:
    object_name: str
    url: str
    backend: str
    size: int


def _object_name(datasource_id: object, filename: str) -> str:
    safe_name = Path(filename).name or "upload.bin"
    return f"{datasource_id}/{uuid_module.uuid4().hex}_{safe_name}"


def _minio_client():
    from minio import Minio

    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL,
    )


def _save_minio(
    content: bytes,
    *,
    object_name: str,
    content_type: str | None,
) -> StoredFile:
    bucket = settings.MINIO_BUCKET_UPLOADS
    client = _minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.put_object(
        bucket,
        object_name,
        BytesIO(content),
        length=len(content),
        content_type=content_type or "application/octet-stream",
    )
    scheme = "https" if settings.MINIO_USE_SSL else "http"
    return StoredFile(
        object_name=object_name,
        url=f"{scheme}://{settings.MINIO_ENDPOINT}/{bucket}/{object_name}",
        backend="minio",
        size=len(content),
    )


def _save_local(content: bytes, *, object_name: str) -> StoredFile:
    root = Path(settings.STORAGE_LOCAL_DIR).resolve()
    target = root / object_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return StoredFile(
        object_name=object_name,
        url=str(target),
        backend="local",
        size=len(content),
    )


def save_upload(
    content: bytes,
    *,
    datasource_id: object,
    filename: str,
    content_type: str | None = None,
) -> StoredFile:
    """保存上传文件：优先 MinIO，``auto`` 模式下失败回退本地。"""
    backend = (settings.STORAGE_BACKEND or "auto").lower()
    object_name = _object_name(datasource_id, filename)

    if backend in ("auto", "minio"):
        try:
            stored = _save_minio(content, object_name=object_name, content_type=content_type)
            logger.info(
                "upload stored backend=minio object={} size={}",
                stored.object_name,
                stored.size,
            )
            return stored
        except Exception as exc:  # noqa: BLE001 - 存储不可用需回退
            if backend == "minio":
                logger.opt(exception=exc).error("MinIO 上传失败（STORAGE_BACKEND=minio）")
                raise
            logger.warning("MinIO 不可用，回退本地存储：{}", exc)

    stored = _save_local(content, object_name=object_name)
    logger.info(
        "upload stored backend=local object={} size={}",
        stored.object_name,
        stored.size,
    )
    return stored


def read_upload(object_name: str, *, backend: str | None = None) -> bytes:
    """读取已存储文件。

    - ``backend='minio'``：只读 MinIO；
    - ``backend='local'``：只读本地；
    - ``auto``（默认）：本地存在则读本地（MinIO 不可用时的回退产物），
      本地不存在则读 MinIO（对象当初成功写入了 MinIO）。
    """
    selected = (backend or settings.STORAGE_BACKEND or "auto").lower()
    local_path = Path(settings.STORAGE_LOCAL_DIR).resolve() / object_name

    if selected == "local" or (selected == "auto" and local_path.is_file()):
        return local_path.read_bytes()

    if selected in ("minio", "auto"):
        bucket = settings.MINIO_BUCKET_UPLOADS
        response = _minio_client().get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    raise FileNotFoundError(f"存储对象不存在：{object_name}")


def save_bytes(
    content: bytes,
    *,
    object_name: str,
    content_type: str | None = None,
) -> StoredFile:
    """保存生成物（报告文件等）：MinIO 优先，``auto`` 模式失败回退本地。"""
    backend = (settings.STORAGE_BACKEND or "auto").lower()

    if backend in ("auto", "minio"):
        try:
            stored = _save_minio(content, object_name=object_name, content_type=content_type)
            logger.info(
                "artifact stored backend=minio object={} size={}",
                stored.object_name,
                stored.size,
            )
            return stored
        except Exception as exc:  # noqa: BLE001
            if backend == "minio":
                logger.opt(exception=exc).error("MinIO 保存失败（STORAGE_BACKEND=minio）")
                raise
            logger.warning("MinIO 不可用，回退本地存储：{}", exc)

    stored = _save_local(content, object_name=object_name)
    logger.info(
        "artifact stored backend=local object={} size={}",
        stored.object_name,
        stored.size,
    )
    return stored


def read_bytes(object_name: str, *, backend: str | None = None) -> bytes:
    """读取生成物（报告文件）；实现与 ``read_upload`` 相同。"""
    return read_upload(object_name, backend=backend)


__all__ = [
    "StoredFile",
    "read_bytes",
    "read_upload",
    "save_bytes",
    "save_upload",
]
