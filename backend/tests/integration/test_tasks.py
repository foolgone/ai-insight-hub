"""B-302 任务管理集成测试（5 态：列表/详情/取消/重试）。"""
from __future__ import annotations

import pytest

from tests.factories import TaskFactory, UserFactory, persist

pytestmark = pytest.mark.integration


async def _make_task(db_session, *, user, **overrides):
    task = TaskFactory(user_id=user.id, **overrides)
    await persist(db_session, task)
    return task


async def test_list_and_detail(client, auth_headers, db_session, test_user) -> None:
    task = await _make_task(db_session, user=test_user, task_type="clean")
    await _make_task(db_session, user=test_user, task_type="evaluate")

    listed = await client.get("/api/v1/tasks", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["pagination"]["total"] == 2
    assert {"id", "task_type", "status", "progress", "created_at"} <= set(body["items"][0])

    filtered = await client.get(
        "/api/v1/tasks", headers=auth_headers, params={"task_type": "clean"}
    )
    assert filtered.json()["pagination"]["total"] == 1

    detail = await client.get(f"/api/v1/tasks/{task.id}", headers=auth_headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["task_type"] == "clean"
    assert detail_body["status"] == "pending"
    assert "estimated_completion" in detail_body
    assert "taskName" not in detail_body


async def test_cancel_pending_task(client, auth_headers, db_session, test_user) -> None:
    task = await _make_task(db_session, user=test_user, status="pending")

    response = await client.post(f"/api/v1/tasks/{task.id}/cancel", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["message"] == "Task cancelled successfully"


async def test_cancel_finished_task_conflict(client, auth_headers, db_session, test_user) -> None:
    task = await _make_task(db_session, user=test_user, status="completed")

    response = await client.post(f"/api/v1/tasks/{task.id}/cancel", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TASK_NOT_CANCELLABLE"


async def test_retry_failed_task(client, auth_headers, db_session, test_user) -> None:
    task = await _make_task(db_session, user=test_user, status="failed", error_message="boom")

    response = await client.post(f"/api/v1/tasks/{task.id}/retry", headers=auth_headers)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["retry_count"] == 1
    assert body["message"] == "Task queued for retry"


async def test_retry_non_failed_task_conflict(client, auth_headers, db_session, test_user) -> None:
    task = await _make_task(db_session, user=test_user, status="running")

    response = await client.post(f"/api/v1/tasks/{task.id}/retry", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TASK_NOT_RETRYABLE"


async def test_task_not_found(client, auth_headers) -> None:
    response = await client.get(
        "/api/v1/tasks/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


async def test_other_user_cannot_read_task(client, auth_headers, db_session) -> None:
    other = UserFactory()
    await persist(db_session, other)
    task = await _make_task(db_session, user=other)

    response = await client.get(f"/api/v1/tasks/{task.id}", headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
