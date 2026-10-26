"""T11 SSE 任务快照单测（不连数据库：序列化字段 + 事件格式）。"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.v1 import tasks as tasks_module
from app.api.v1.tasks import _task_snapshot
from app.models import Task

pytestmark = pytest.mark.unit


def test_task_snapshot_contains_minimal_fields() -> None:
    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        task_type="clean",
        status="running",
        progress=42,
        current_step="cleaning",
        error_message=None,
        completed_at=None,
    )

    snapshot = _task_snapshot(task)

    assert snapshot == {
        "id": str(task_id),
        "task_type": "clean",
        "status": "running",
        "progress": 42,
        "current_step": "cleaning",
        "error_message": None,
        "completed_at": None,
    }


def test_task_snapshot_formats_completed_at() -> None:
    task = Task(
        id=uuid.uuid4(),
        task_type="evaluate",
        status="completed",
        progress=100,
        completed_at=datetime(2026, 10, 26, 12, 0, 0),
    )

    snapshot = _task_snapshot(task)

    assert snapshot["completed_at"] == "2026-10-26T12:00:00"
    assert snapshot["progress"] == 100


async def test_stream_generator_emits_tasks_event(monkeypatch) -> None:
    """SSE 事件格式：event=tasks + data=JSON；不依赖真实数据库/HTTP 流。"""

    async def fake_snapshots(user):  # noqa: ANN001, ARG001
        return [{"id": "t-1", "status": "running", "progress": 42}]

    async def never_disconnected() -> bool:
        return False

    monkeypatch.setattr(tasks_module, "_task_snapshots", fake_snapshots)
    request = SimpleNamespace(is_disconnected=never_disconnected)
    user = SimpleNamespace(id=uuid.uuid4(), role="user")

    response = await tasks_module.stream_tasks(request, user)  # type: ignore[arg-type]

    assert response.media_type == "text/event-stream"
    assert response.headers["x-accel-buffering"] == "no"
    chunk = await asyncio.wait_for(response.body_iterator.__anext__(), timeout=5)
    await response.body_iterator.aclose()

    assert chunk.startswith("event: tasks\ndata: ")
    payload = json.loads(chunk.split("data: ", 1)[1].strip())
    assert payload["items"][0]["id"] == "t-1"
