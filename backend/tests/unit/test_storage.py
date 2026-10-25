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


def test_save_and_read_local(local_storage: Path) -> None:
    stored = storage_service.save_upload(
        b"hello-storage",
        datasource_id="ds-1",
        filename="data.csv",
        content_type="text/csv",
    )

    assert stored.backend == "local"
    assert stored.size == len(b"hello-storage")
    assert Path(stored.url).is_file()
    assert storage_service.read_upload(stored.object_name, backend="local") == (b"hello-storage")


def test_object_name_strips_directory_traversal(local_storage: Path) -> None:
    stored = storage_service.save_upload(b"x", datasource_id="ds-2", filename="../../etc/passwd")

    assert ".." not in stored.object_name
    assert stored.object_name.endswith("passwd")


def test_auto_falls_back_to_local_when_minio_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "auto")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))

    def _broken_minio(*args, **kwargs):
        raise ConnectionError("minio down")

    monkeypatch.setattr(storage_service, "_save_minio", _broken_minio)

    stored = storage_service.save_upload(b"fallback", datasource_id="ds-3", filename="a.txt")

    assert stored.backend == "local"
    assert Path(stored.url).is_file()


def test_minio_strict_mode_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "minio")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))

    def _broken_minio(*args, **kwargs):
        raise ConnectionError("minio down")

    monkeypatch.setattr(storage_service, "_save_minio", _broken_minio)

    with pytest.raises(ConnectionError):
        storage_service.save_upload(b"fail", datasource_id="ds-4", filename="a.txt")
