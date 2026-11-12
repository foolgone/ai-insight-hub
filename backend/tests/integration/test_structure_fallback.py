"""切分任务兜底：短音频 / 关闭结构化时保留整段文本（不判失败、不丢数据）。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import CleanedData
from app.services import structure_task_service
from tests.factories import DataSourceFactory, RawDataFactory, TaskFactory, UserFactory, persist

pytestmark = pytest.mark.integration


async def _short_media_raw(session, *, user, text: str = "面试官：你好。候选人：你好。"):
    datasource = DataSourceFactory(user_id=user.id)
    await persist(session, datasource)
    raw = RawDataFactory(
        datasource_id=datasource.id,
        raw_content={
            "format": "media",
            "text": text,
            "media": {"channel_mode": "mono", "duration": 8.0, "channels": 1},
            "asr": {"status": "completed"},
            "records": [
                {
                    "dialogue_id": "asr-1",
                    "timestamp": None,
                    "user_message": text,
                    "ai_response": "",
                    "quality_score": None,
                    "issues": ["asr_transcript", "mono_speaker_unknown"],
                    "speaker_pair": "mono",
                }
            ],
        },
        file_info={"filename": "short.mp3", "size": 1024},
    )
    await persist(session, raw)
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="structure",
        status="pending",
        params={"raw_data_id": str(raw.id)},
    )
    await persist(session, task)
    return datasource, raw, task


async def _rows(session, datasource_id: uuid.UUID) -> list[CleanedData]:
    return list(
        (
            await session.execute(
                select(CleanedData).where(CleanedData.datasource_id == datasource_id)
            )
        )
        .scalars()
        .all()
    )


async def test_short_audio_falls_back_to_single_record(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource, raw, task = await _short_media_raw(db_session, user=user, text="太短了，只有一句。")

    result = await structure_task_service.run_structure_task(str(task.id), session=db_session)

    assert result["status"] == "completed"
    assert result["created"] == 1
    assert result["structure"]["skipped_reason"] == "text_too_short"

    rows = await _rows(db_session, datasource.id)
    assert len(rows) == 1
    assert rows[0].user_message == "太短了，只有一句。"
    assert rows[0].ai_response == ""
    assert "structure_unparsed" in rows[0].issues

    await db_session.refresh(raw)
    state = structure_task_service.structure_state(raw)
    assert state["structure_status"] == "skipped"
    assert "已保留整段文本" in state["note"]


async def test_fallback_replaces_previous_rows(db_session) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource, raw, task = await _short_media_raw(db_session, user=user)

    await structure_task_service.run_structure_task(str(task.id), session=db_session)
    again = await structure_task_service.run_structure_task(str(task.id), session=db_session)

    assert again["created"] == 1
    assert again["replaced"] == 1
    assert len(await _rows(db_session, datasource.id)) == 1


async def test_disabled_structure_falls_back_instead_of_failing(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "MEDIA_STRUCTURE_ENABLED", False)
    user = UserFactory()
    await persist(db_session, user)
    datasource, raw, task = await _short_media_raw(
        db_session, user=user, text="这段其实足够长，但功能被关闭了。" * 20
    )

    result = await structure_task_service.run_structure_task(str(task.id), session=db_session)

    assert result["status"] == "completed"
    assert result["structure"]["skipped_reason"] == "structure_disabled"
    assert len(await _rows(db_session, datasource.id)) == 1


async def test_structure_success_clears_skip_marker(db_session, monkeypatch) -> None:
    """兜底之后再成功切分：标记清掉、状态变 done。"""
    user = UserFactory()
    await persist(db_session, user)
    datasource, raw, task = await _short_media_raw(db_session, user=user, text="短文本。")

    await structure_task_service.run_structure_task(str(task.id), session=db_session)
    await db_session.refresh(raw)
    assert structure_task_service.structure_state(raw)["structure_status"] == "skipped"

    # 让同一 raw 具备切分条件后重跑（模拟后续补足文本）
    raw.raw_content = {
        **raw.raw_content,
        "text": "面试官：请自我介绍。候选人：我做后端开发。" * 30,
        "records": [
            {
                "dialogue_id": "asr-1",
                "timestamp": None,
                "user_message": "整段",
                "ai_response": "",
                "speaker_pair": "mono",
                "issues": ["asr_transcript"],
            }
        ],
    }
    await db_session.flush()

    class _FakeAgent:
        async def structure(self, input_data, **kwargs):
            from app.agents.base import AgentResult

            return AgentResult(
                success=True,
                data={
                    "content_type": "interview",
                    "structure": "qa",
                    "confidence": 0.9,
                    "qa": [{"question": "请自我介绍", "answer": "我做后端开发"}],
                },
                metadata={"agent": "structure_agent", "version": "v1.1.0", "model": "fake"},
                duration=1.0,
                token_usage={"input": 10, "output": 10},
            )

    monkeypatch.setattr(
        structure_task_service.structure_service, "_build_agent", lambda *_: _FakeAgent()
    )

    result = await structure_task_service.run_structure_task(str(task.id), session=db_session)

    assert result["status"] == "completed"
    assert result["created"] == 1
    await db_session.refresh(raw)
    assert "structure_skipped" not in (raw.raw_content or {})
    assert structure_task_service.structure_state(raw)["structure_status"] == "done"
