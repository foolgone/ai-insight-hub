"""B-314 清洗执行集成测试（run_clean_task → cleaned_data / 状态推进）。"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.models import CleanedData
from app.services import cleaning_service
from tests.factories import (
    DataSourceFactory,
    RawDataFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration


def _dialogues() -> list[dict[str, Any]]:
    return [
        {
            "dialogue_id": "line-1",
            "timestamp": "2025-01-15T10:30:00",
            "user_message": "iPhone 14 多少钱",
            "ai_response": "5999 元起",
            "quality_score": 95,
            "issues": [],
        },
        {
            "dialogue_id": "line-2",
            "timestamp": None,
            "user_message": "可以分期吗",
            "ai_response": "支持花呗 12 期",
            "quality_score": 85,
            "issues": ["missing_timestamp"],
        },
    ]


class _FakeAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def clean(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _success_result() -> AgentResult:
    return AgentResult(
        success=True,
        data={"dialogues": _dialogues()},
        metadata={"version": "v1.0.0"},
        duration=1.5,
        token_usage={"input": 100, "output": 50},
    )


async def _setup(db_session, *, status: str = "pending") -> tuple:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(
        datasource_id=datasource.id,
        raw_content={"text": "客户：你好 客服：您好", "format": "txt"},
    )
    await persist(db_session, raw)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="clean",
        status=status,
        params={"raw_data_id": str(raw.id)},
    )
    await persist(db_session, task)
    return user, datasource, raw, task


async def test_run_clean_task_writes_cleaned_data(db_session, monkeypatch) -> None:
    _, datasource, raw, task = await _setup(db_session)
    monkeypatch.setattr(cleaning_service, "_build_agent", lambda: _FakeAgent(_success_result()))

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    assert outcome["cleaned_records"] == 2

    rows = (
        (
            await db_session.execute(
                select(CleanedData).where(CleanedData.datasource_id == datasource.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert {row.quality_score for row in rows} == {95.0, 85.0}
    assert all(isinstance(row.dialogue_id, uuid.UUID) for row in rows)
    assert rows[0].raw_data_id == raw.id

    await db_session.refresh(raw)
    assert raw.status == "completed"
    assert raw.processed_at is not None

    await db_session.refresh(datasource)
    assert datasource.workflow_status == "data_cleaned"
    assert datasource.statistics["cleaned_records"] == 2
    assert datasource.statistics["quality_score_avg"] == 90.0

    await db_session.refresh(task)
    assert task.status == "completed"
    assert task.progress == 100
    assert task.result["cleaned_records"] == 2


async def test_run_clean_task_marks_failed_when_agent_fails(db_session, monkeypatch) -> None:
    _, _, raw, task = await _setup(db_session)
    failed = AgentResult(success=False, errors=["llm failed"])
    monkeypatch.setattr(cleaning_service, "_build_agent", lambda: _FakeAgent(failed))

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"
    await db_session.refresh(raw)
    assert raw.status == "failed"
    assert "llm failed" in (raw.error_message or "")
    await db_session.refresh(task)
    assert task.status == "failed"


async def test_run_clean_task_without_raw_data_fails(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="clean",
        status="pending",
        params={},
    )
    await persist(db_session, task)

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "failed"
    await db_session.refresh(task)
    assert "no raw data" in (task.error_message or "")


async def test_run_clean_task_skips_cancelled_task(db_session) -> None:
    _, _, _, task = await _setup(db_session, status="cancelled")

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "cancelled"


async def test_run_clean_task_missing_task(db_session) -> None:
    outcome = await cleaning_service.run_clean_task(str(uuid.uuid4()), session=db_session)

    assert outcome["status"] == "missing"
