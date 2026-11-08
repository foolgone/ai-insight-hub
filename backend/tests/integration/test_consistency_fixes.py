"""阶段一一致性修复的集成测试（真实 PostgreSQL）。

覆盖：
- 洞察结果写入 ``analysis_results``（P0-1）
- 报告创建同步建 ``tasks``（P0-5）
- 清洗重跑幂等：唯一索引 + ON CONFLICT DO NOTHING，不重复插入且任务不失败（P1-5）
- 成本幂等键带 scope：同任务多次调用落多行（P0-2）
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, update

from app.agents.base import AgentResult
from app.core.cost_tracker import CostTracker
from app.core.llm import LLMResponse, LLMUsage
from app.models import AnalysisResult, CleanedData, LlmCall, Task
from app.services import cleaning_service, insight_service, report_service
from tests.factories import (
    CleanedDataFactory,
    DataSourceFactory,
    RawDataFactory,
    TaskFactory,
    UserFactory,
    persist,
)

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------- P0-1


class _InsightAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def analyze(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _insight_result() -> AgentResult:
    return AgentResult(
        success=True,
        data={
            "intent_distribution": {"咨询": 2},
            "top_questions": [{"question": "退货政策", "count": 2}],
            "sentiment_distribution": {"正面": 0.5, "中性": 0.5, "负面": 0.0},
            "sentiment_trend": [],
            "pain_points": [],
            "unresolved_issues": [],
            "emerging_topics": [],
            "seasonal_patterns": None,
            "degraded": False,
        },
        metadata={"agent": "insight_agent", "version": "v1.0.0"},
        duration=1.0,
        token_usage={"input": 200, "output": 100},
    )


async def test_insight_persists_analysis_result(db_session, monkeypatch) -> None:
    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    for index in range(2):
        await persist(
            db_session,
            CleanedDataFactory(
                datasource_id=datasource.id,
                raw_data_id=raw.id,
                user_message=f"怎么退货 {index}",
                ai_response="在订单页申请",
            ),
        )
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="analyze",
        status="pending",
        params={},
    )
    await persist(db_session, task)
    monkeypatch.setattr(insight_service, "_build_agent", lambda: _InsightAgent(_insight_result()))

    outcome = await insight_service.run_insight_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    row = (
        await db_session.execute(
            select(AnalysisResult).where(
                AnalysisResult.datasource_id == datasource.id,
                AnalysisResult.analysis_type == "insight",
            )
        )
    ).scalar_one()
    assert row.data_id is None  # 数据源级结果
    assert row.result["intent_distribution"] == {"咨询": 2}
    assert row.agent_name == "insight_agent"
    assert row.cost is not None


# --------------------------------------------------------------------- P0-5


async def test_create_report_creates_task(client, auth_headers, db_session, monkeypatch) -> None:
    monkeypatch.setattr(report_service, "enqueue_report", lambda report: "celery-report-1")
    created_ds = await client.post(
        "/api/v1/datasources",
        headers=auth_headers,
        json={"name": "report-task-ds", "type": "customer_service"},
    )
    datasource_id = created_ds.json()["id"]

    response = await client.post(
        f"/api/v1/datasources/{datasource_id}/reports",
        headers=auth_headers,
        json={"title": "任务化报告", "report_type": "quality", "format": "markdown"},
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["task_id"]

    task = await db_session.get(Task, uuid.UUID(body["task_id"]))
    assert task is not None
    assert task.task_type == "report"
    assert task.params["report_id"] == body["id"]
    assert task.celery_task_id == "celery-report-1"


# --------------------------------------------------------------------- P1-5


class _CleaningAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def clean(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _cleaning_result() -> AgentResult:
    return AgentResult(
        success=True,
        data={
            "dialogues": [
                {
                    "dialogue_id": "line-1",
                    "timestamp": "2025-01-15T10:30:00",
                    "user_message": "iPhone 14 多少钱",
                    "ai_response": "5999 元起",
                    "quality_score": 95,
                    "issues": [],
                }
            ]
        },
        metadata={"version": "v1.0.0"},
        duration=0.5,
        token_usage={"input": 10, "output": 5},
    )


async def _cleaning_setup(db_session) -> tuple:
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
        status="pending",
        params={"raw_data_id": str(raw.id)},
    )
    await persist(db_session, task)
    return datasource, raw, task


async def test_clean_rerun_is_idempotent(db_session, monkeypatch) -> None:
    datasource, raw, task = await _cleaning_setup(db_session)
    monkeypatch.setattr(
        cleaning_service, "_build_agent", lambda: _CleaningAgent(_cleaning_result())
    )

    first = await cleaning_service.run_clean_task(str(task.id), session=db_session)
    assert first["status"] == "completed"
    assert first["cleaned_records"] == 1

    second = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    # 重跑全部命中唯一索引：0 条新增，但任务仍成功
    assert second["status"] == "completed"
    assert second["cleaned_records"] == 0
    rows = (
        (await db_session.execute(select(CleanedData).where(CleanedData.raw_data_id == raw.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    await db_session.refresh(task)
    assert task.result["skipped_existing_records"] == 1


async def test_cleaning_missing_timestamp_stored_as_null(db_session, monkeypatch) -> None:
    """时间戳缺失存 NULL 并打 missing_timestamp 标签（P1-6）。"""
    _, raw, task = await _cleaning_setup(db_session)
    result = _cleaning_result()
    result.data["dialogues"][0]["timestamp"] = None
    result.data["dialogues"][0]["issues"] = []
    monkeypatch.setattr(cleaning_service, "_build_agent", lambda: _CleaningAgent(result))

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "completed"
    row = (
        await db_session.execute(select(CleanedData).where(CleanedData.raw_data_id == raw.id))
    ).scalar_one()
    assert row.timestamp is None
    assert "missing_timestamp" in (row.issues or [])


async def test_clean_finalize_preserves_cancelled(db_session, monkeypatch) -> None:
    """收尾前复查取消：最后一条处理完时被取消，不得覆盖为 completed。"""
    from app.services import task_service

    _, _, task = await _cleaning_setup(db_session)
    monkeypatch.setattr(
        cleaning_service, "_build_agent", lambda: _CleaningAgent(_cleaning_result())
    )

    async def fake_is_cancelled(session, task_id):
        await session.execute(update(Task).where(Task.id == task_id).values(status="cancelled"))
        return True

    monkeypatch.setattr(task_service, "is_cancelled", fake_is_cancelled)

    outcome = await cleaning_service.run_clean_task(str(task.id), session=db_session)

    assert outcome["status"] == "cancelled"
    await db_session.refresh(task)
    assert task.status == "cancelled"


class _EvaluationAgent:
    def __init__(self, result: AgentResult) -> None:
        self._result = result

    async def evaluate(self, input_data, **kwargs) -> AgentResult:
        return self._result


def _evaluation_result() -> AgentResult:
    return AgentResult(
        success=True,
        data={
            "overall_score": 80,
            "needs_review": False,
            "quality_level": "good",
            "dimensions": {},
        },
        metadata={"agent": "evaluation_agent", "version": "v1.0.0"},
        duration=0.1,
        token_usage={"input": 10, "output": 5},
    )


async def test_evaluation_finalize_preserves_cancelled(db_session, monkeypatch) -> None:
    from app.services import evaluation_service, task_service

    user = UserFactory()
    await persist(db_session, user)
    datasource = DataSourceFactory(user_id=user.id)
    await persist(db_session, datasource)
    raw = RawDataFactory(datasource_id=datasource.id)
    await persist(db_session, raw)
    await persist(
        db_session,
        CleanedDataFactory(
            datasource_id=datasource.id,
            raw_data_id=raw.id,
            user_message="退货怎么处理",
            ai_response="7 天无理由",
        ),
    )
    task = TaskFactory(
        user_id=user.id,
        datasource_id=datasource.id,
        task_type="evaluate",
        status="pending",
        params={},
    )
    await persist(db_session, task)
    monkeypatch.setattr(
        evaluation_service, "_build_agent", lambda: _EvaluationAgent(_evaluation_result())
    )

    async def fake_is_cancelled(session, task_id):
        await session.execute(update(Task).where(Task.id == task_id).values(status="cancelled"))
        return True

    monkeypatch.setattr(task_service, "is_cancelled", fake_is_cancelled)

    outcome = await evaluation_service.run_evaluation_task(str(task.id), session=db_session)

    assert outcome["status"] == "cancelled"
    await db_session.refresh(task)
    assert task.status == "cancelled"


# --------------------------------------------------------------------- P0-2


async def test_cost_tracker_scope_keeps_multiple_rows(db_session) -> None:
    task_id = uuid.uuid4()
    tracker = CostTracker(db_session)
    for scope in ("clean:raw-a", "clean:raw-b", "clean:raw-c"):
        await tracker.track(
            response=LLMResponse(
                content="",
                usage=LLMUsage(input_tokens=10, output_tokens=5),
                model="fake-model",
                latency_ms=10.0,
            ),
            task_id=task_id,
            scope=scope,
            agent_name="cleaning_agent",
        )

    rows = (
        (await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 3
    assert {row.idempotency_key for row in rows} == {
        f"{task_id}:clean:raw-a:0",
        f"{task_id}:clean:raw-b:0",
        f"{task_id}:clean:raw-c:0",
    }


async def test_cost_tracker_same_scope_upserts_one_row(db_session) -> None:
    task_id = uuid.uuid4()
    tracker = CostTracker(db_session)
    for _ in range(2):
        await tracker.track(
            response=LLMResponse(
                content="",
                usage=LLMUsage(input_tokens=10, output_tokens=5),
                model="fake-model",
                latency_ms=10.0,
            ),
            task_id=task_id,
            scope="insight",
            agent_name="insight_agent",
        )

    rows = (
        (await db_session.execute(select(LlmCall).where(LlmCall.task_id == task_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].idempotency_key == f"{task_id}:insight:0"
