"""对象存储端口：上传原始文件、读取原始文件、保存/读取生成物。"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StoredFileLike(Protocol):
    """存储返回值的结构：对象名 + 可访问 URL + 后端标识 + 大小。"""

    object_name: str
    url: str
    backend: str
    size: int


@runtime_checkable
class StoragePort(Protocol):
    """存储接口。

    ``app.services.storage_service`` 是模块级函数实现，模块对象本身即满足本协议
    （可直接把模块当实现注入，无需包一层类）。
    """

    def save_upload(
        self,
        content: bytes,
        *,
        datasource_id: Any,
        filename: str,
        content_type: str | None = None,
    ) -> StoredFileLike:
        ...

    def read_upload(self, object_name: str, *, backend: str | None = None) -> bytes:
        ...

    def save_bytes(
        self,
        content: bytes,
        *,
        object_name: str,
        content_type: str | None = None,
    ) -> StoredFileLike:
        ...

    def read_bytes(self, object_name: str, *, backend: str | None = None) -> bytes:
        ...


__all__ = ["StoragePort", "StoredFileLike"]
