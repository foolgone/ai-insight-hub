"""B-305 清洗编排 service 层测试（护栏/计数/worker 骨架）。"""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import TaskAlreadyRunningError
from app.services import cleaning_service
from tests.factories import (
    DataSourceFactory,
    RawDataFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration


async def _datasource(db_session):
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    return user, datasource


async def test_ensure_no_running_task_allows_idle_datasource(db_session) -> None:
    _, datasource = await _datasource(db_session)

    await cleaning_service.ensure_no_running_task(db_session, datasource_id=datasource.id)


async def test_ensure_no_running_task_rejects_active_task(db_session) -> None:
    user, datasource = await _datasource(db_session)
    await persist(
        db_session,
        TaskFactory(
            user_id=user.id,
            datasource_id=datasource.id,
            task_type="clean",
            status="running",
        ),
    )

    with pytest.raises(TaskAlreadyRunningError):
        await cleaning_service.ensure_no_running_task(db_session, datasource_id=datasource.id)


async def test_count_pending_records(db_session) -> None:
    _, datasource = await _datasource(db_session)
    await persist(
        db_session,
        RawDataFactory(datasource_id=datasource.id, status="pending"),
        RawDataFactory(datasource_id=datasource.id, status="completed"),
        RawDataFactory(datasource_id=datasource.id, status="failed"),
    )

    count = await cleaning_service.count_pending_records(db_session, datasource.id)

    # 失败文件也算「可清洗」：否则用户只能重新上传（2026-11-13 E2E 反馈）
    assert count == 2


async def test_load_raw_items_includes_failed(db_session) -> None:
    user, datasource = await _datasource(db_session)
    failed = RawDataFactory(datasource_id=datasource.id, status="failed")
    pending = RawDataFactory(datasource_id=datasource.id, status="pending")
    done = RawDataFactory(datasource_id=datasource.id, status="completed")
    await persist(db_session, failed, pending, done)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="clean",
        status="pending",
        params={},
    )
    await persist(db_session, task)

    items = await cleaning_service._load_raw_items(db_session, task)  # noqa: SLF001

    assert {item.id for item in items} == {failed.id, pending.id}


async def test_create_clean_task_persists_params(db_session) -> None:
    user, datasource = await _datasource(db_session)

    task = await cleaning_service.create_clean_task(
        db_session,
        user=user,
        datasource_id=datasource.id,
        task_name="测试清洗",
        params={"data_ids": [], "config": {"remove_duplicates": True}},
    )

    assert task.id is not None
    assert task.task_type == "clean"
    assert task.status == "pending"
    assert task.user_id == user.id
    assert task.params["config"]["remove_duplicates"] is True


async def test_run_clean_task_missing_task_returns_missing() -> None:
    result = await cleaning_service.run_clean_task(str(uuid.uuid4()))

    assert result["status"] == "missing"
