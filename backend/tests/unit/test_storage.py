"""B-304 存储服务测试（本地回退 / MinIO 不可用降级 / 路径安全）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services import storage_service

pytestmark = pytest.mark.unit


@pytest.fixture()
def local_storage(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))
    return tmp_path


def test_save_upload_from_path_moves_file(local_storage: Path, tmp_path: Path) -> None:
    """流式落盘路径：临时文件被移动到存储目录，调用方无需再读进内存。"""
    source = tmp_path / "streamed.tmp"
    source.write_bytes(b"streamed-content")

    stored = storage_service.save_upload_from_path(
        source,
        tenant_id="tenant-1",
        datasource_id="ds-1",
        filename="big.mp3",
        content_type="audio/mpeg",
    )

    assert stored.backend == "local"
    assert stored.size == len(b"streamed-content")
    assert not source.exists()
    assert storage_service.read_upload(stored.object_name) == b"streamed-content"


def test_save_and_read_local(local_storage: Path) -> None:
    stored = storage_service.save_upload(
        b"hello-storage",
        tenant_id="tenant-1",
        datasource_id="ds-1",
        filename="data.csv",
        content_type="text/csv",
    )

    assert stored.backend == "local"
    assert stored.size == len(b"hello-storage")
    assert Path(stored.url).is_file()
    assert storage_service.read_upload(stored.object_name, backend="local") == (b"hello-storage")


def test_object_name_strips_directory_traversal(local_storage: Path) -> None:
    stored = storage_service.save_upload(
        b"x", tenant_id="tenant-2", datasource_id="ds-2", filename="../../etc/passwd"
    )

    assert stored.object_name.startswith("tenant/tenant-2/uploads/ds-2/")
    assert ".." not in stored.object_name
    assert stored.object_name.endswith("passwd")


def test_auto_falls_back_to_local_when_minio_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "auto")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))

    def _broken_minio(*args, **kwargs):
        raise ConnectionError("minio down")

    monkeypatch.setattr(storage_service, "_save_minio", _broken_minio)

    stored = storage_service.save_upload(
        b"fallback", tenant_id="tenant-3", datasource_id="ds-3", filename="a.txt"
    )

    assert stored.backend == "local"
    assert Path(stored.url).is_file()


def test_minio_strict_mode_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "minio")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))

    def _broken_minio(*args, **kwargs):
        raise ConnectionError("minio down")

    monkeypatch.setattr(storage_service, "_save_minio", _broken_minio)

    with pytest.raises(ConnectionError):
        storage_service.save_upload(
            b"fail", tenant_id="tenant-4", datasource_id="ds-4", filename="a.txt"
        )


def test_auto_read_prefers_local_when_present(tmp_path: Path, monkeypatch) -> None:
    """MinIO 不可用时写入本地的对象，auto 读取应直接命中本地（不访问 MinIO）。"""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "auto")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))
    target = tmp_path / "reports" / "r1.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"local-report")

    def _unexpected_minio():
        raise AssertionError("auto 读取本地命中时不应访问 MinIO")

    monkeypatch.setattr(storage_service, "_minio_client", _unexpected_minio)

    assert storage_service.read_bytes("reports/r1.md") == b"local-report"


def test_auto_read_falls_back_to_minio_when_local_missing(tmp_path: Path, monkeypatch) -> None:
    """对象当初写入 MinIO（本地无副本）时，auto 读取应回退到 MinIO。"""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "auto")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))

    class _Response:
        def read(self) -> bytes:
            return b"minio-report"

        def close(self) -> None:
            ...

        def release_conn(self) -> None:
            ...

    class _Client:
        def get_object(self, bucket: str, object_name: str) -> _Response:
            assert bucket == settings.MINIO_BUCKET_UPLOADS
            assert object_name == "reports/r2.md"
            return _Response()

    monkeypatch.setattr(storage_service, "_minio_client", lambda: _Client())

    assert storage_service.read_bytes("reports/r2.md") == b"minio-report"


def test_legacy_key_still_readable(local_storage: Path) -> None:
    """旧对象保留旧 key（无 tenant 前缀），读取路径继续兼容。"""
    legacy_key = "legacy-ds/legacy-report.md"
    storage_service.save_bytes(
        b"legacy-report", object_name=legacy_key, content_type="text/markdown"
    )

    assert storage_service.read_upload(legacy_key) == b"legacy-report"
