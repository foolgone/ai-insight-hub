"""切分产物（知识点 / 摘要）按文件整体替换 —— 多次切分不累积重复。"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentResult
from app.application import structure_service
from app.models import AnalysisResult, KnowledgeBase
from app.services import structure_task_service
from tests.factories import DataSourceFactory, RawDataFactory, TaskFactory, UserFactory, persist

pytestmark = pytest.mark.integration

_TEXT = "这是一段用于切分的转写文本，讨论了索引失效的排查方法。" * 20

_KNOWLEDGE = {
    "content_type": "monologue",
    "structure": "knowledge",
    "confidence": 0.8,
    "knowledge": [{"title": "索引失效排查", "content": "先看执行计划，再看选择性", "tags": ["db"]}],
}

_SUMMARY = {
    "content_type": "meeting",
    "structure": "summary",
    "confidence": 0.7,
    "summary": "讨论了数据库优化，结论是先做索引评估。",
}

_QA = {
    "content_type": "interview",
    "structure": "qa",
    "confidence": 0.9,
    "qa": [{"question": "索引失效怎么查？", "answer": "先看执行计划", "quality_score": 80}],
}


class _FakeAgent:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def structure(self, input_data, **kwargs) -> AgentResult:
        return AgentResult(
            success=True,
            data=dict(self._payload),
            metadata={"agent": "structure_agent", "version": "v1.1.0", "model": "fake"},
            duration=1.0,
            token_usage={"input": 10, "output": 10},
        )


async def _setup(db_session) -> tuple:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(
        datasource_id=datasource.id,
        raw_content={
            "format": "media",
            "text": _TEXT,
            "media": {"channel_mode": "mono", "duration": 60.0, "channels": 1},
            "asr": {"status": "completed"},
            "records": [
                {
                    "dialogue_id": "asr-1",
                    "user_message": _TEXT,
                    "ai_response": "",
                    "speaker_pair": "mono",
                    "issues": ["asr_transcript"],
                }
            ],
        },
        file_info={"filename": "call.mp3", "size": 1024},
    )
    await persist(db_session, raw)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="structure",
        status="pending",
        params={"raw_data_id": str(raw.id)},
    )
    await persist(db_session, task)
    return datasource, raw, task


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    return int(await session.scalar(stmt) or 0)


async def test_knowledge_artifacts_are_replaced_on_rerun(db_session, monkeypatch) -> None:
    datasource, raw, task = await _setup(db_session)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(_KNOWLEDGE))

    first = await structure_task_service.run_structure_task(str(task.id), session=db_session)
    assert first["status"] == "completed"
    assert await _count(db_session, KnowledgeBase, raw_data_id=raw.id) == 1

    second = await structure_task_service.run_structure_task(str(task.id), session=db_session)
    assert second["status"] == "completed"
    assert second["replaced_artifacts"]["knowledge"] == 1
    # 仍然只有 1 条（替换，不累积）
    assert await _count(db_session, KnowledgeBase, raw_data_id=raw.id) == 1


async def test_summary_artifacts_are_replaced_on_rerun(db_session, monkeypatch) -> None:
    datasource, raw, task = await _setup(db_session)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(_SUMMARY))

    await structure_task_service.run_structure_task(str(task.id), session=db_session)
    assert await _count(db_session, AnalysisResult, raw_data_id=raw.id, analysis_type="other") == 1

    second = await structure_task_service.run_structure_task(str(task.id), session=db_session)
    assert second["replaced_artifacts"]["summary"] == 1
    assert await _count(db_session, AnalysisResult, raw_data_id=raw.id, analysis_type="other") == 1


async def test_switching_kind_removes_previous_artifacts(db_session, monkeypatch) -> None:
    """先切出知识点，后来改成 qa：旧知识点应被清掉，不留孤儿。"""
    datasource, raw, task = await _setup(db_session)
    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(_KNOWLEDGE))
    await structure_task_service.run_structure_task(str(task.id), session=db_session)
    assert await _count(db_session, KnowledgeBase, raw_data_id=raw.id) == 1

    monkeypatch.setattr(structure_service, "_build_agent", lambda *_: _FakeAgent(_QA))
    result = await structure_task_service.run_structure_task(str(task.id), session=db_session)

    assert result["status"] == "completed"
    assert result["created"] == 1
    assert await _count(db_session, KnowledgeBase, raw_data_id=raw.id) == 0
