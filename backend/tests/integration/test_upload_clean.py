"""B-305 上传与清洗入队集成测试（413/415/409/202、raw_data 落库、celery_task_id 回写）。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.models import DataSource, RawData, Task
from app.services import cleaning_service
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

CSV_CONTENT = "user_message,ai_response\n你好,您好\n多少钱,5999 元\n".encode()


async def _create_datasource(client, headers) -> str:
    response = await client.post(
        "/api/v1/datasources",
        headers=headers,
        json={"name": "upload-ds", "type": "customer_service"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _local_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_DIR", str(tmp_path))


async def test_upload_creates_raw_data_and_task(
    client, auth_headers, db_session, monkeypatch, tmp_path
) -> None:
    _local_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(cleaning_service, "enqueue_clean", lambda task: "fake-celery-id")
    datasource_id = await _create_datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("data.csv", CSV_CONTENT, "text/csv")},
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["file_info"]["filename"] == "data.csv"
    assert body["file_info"]["size"] == len(CSV_CONTENT)
    assert body["file_info"]["storage_backend"] == "local"

    task = await db_session.get(Task, uuid.UUID(body["task_id"]))
    assert task is not None
    assert task.task_type == "clean"
    assert task.status == "pending"
    assert task.celery_task_id == "fake-celery-id"

    rows = (
        await db_session.execute(
            select(RawData).where(RawData.datasource_id == uuid.UUID(datasource_id))
        )
    ).scalars()
    raw_data = list(rows)
    assert len(raw_data) == 1
    assert raw_data[0].status == "pending"
    assert raw_data[0].file_info["filename"] == "data.csv"
    assert raw_data[0].raw_content["record_count"] == 2

    datasource = await db_session.get(DataSource, uuid.UUID(datasource_id))
    assert datasource.workflow_status == "data_uploaded"


async def test_upload_rejects_unsupported_format(client, auth_headers, monkeypatch) -> None:
    datasource_id = await _create_datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("data.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "FILE_FORMAT_INVALID"


async def test_upload_rejects_oversize_file(client, auth_headers, monkeypatch, tmp_path) -> None:
    _local_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    datasource_id = await _create_datasource(client, auth_headers)

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/upload",
        headers=auth_headers,
        files={"file": ("data.csv", CSV_CONTENT, "text/csv")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_upload_missing_datasource_404(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/datasources/00000000-0000-0000-0000-000000000000/upload",
        headers=auth_headers,
        files={"file": ("data.csv", CSV_CONTENT, "text/csv")},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DATASOURCE_NOT_FOUND"


async def test_upload_viewer_forbidden(client, db_session) -> None:
    viewer = UserFactory(password_hash=hash_password("viewer123"), role="viewer")
    await persist(db_session, viewer)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": viewer.email, "password": "viewer123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    datasource = await client.post(
        "/api/v1/datasources",
        headers=headers,
        json={"name": "x", "type": "other"},
    )
    # viewer 不能创建数据源（403）
    assert datasource.status_code == 403

    response = await client.post(
        "/api/v1/datasources/00000000-0000-0000-0000-000000000000/upload",
        headers=headers,
        files={"file": ("data.csv", CSV_CONTENT, "text/csv")},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_clean_enqueues_and_guards_duplicate(
    client, auth_headers, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(cleaning_service, "enqueue_clean", lambda task: "clean-celery-id")
    datasource_id = await _create_datasource(client, auth_headers)

    first = await client.post(
        f"/api/v1/datasources/{datasource_id}/clean",
        headers=auth_headers,
        json={"config": {"remove_duplicates": True}},
    )
    assert first.status_code == 202, first.text
    body = first.json()
    assert body["message"] == "Cleaning task queued"
    assert body["estimated_duration"] >= 5.0

    task = await db_session.get(Task, uuid.UUID(body["task_id"]))
    assert task is not None and task.celery_task_id == "clean-celery-id"

    second = await client.post(
        f"/api/v1/datasources/{datasource_id}/clean",
        headers=auth_headers,
        json={},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "TASK_ALREADY_RUNNING"


async def test_clean_other_user_forbidden(client, auth_headers, db_session, monkeypatch) -> None:
    monkeypatch.setattr(cleaning_service, "enqueue_clean", lambda task: "id")
    datasource_id = await _create_datasource(client, auth_headers)

    other = UserFactory(password_hash=hash_password("other12345"))
    await persist(db_session, other)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "other12345"},
    )
    token = login.json()["access_token"]

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/clean",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
