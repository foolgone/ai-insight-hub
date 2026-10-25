"""洞察分析服务（B-603；API 设计 §7.3 / §7.4）。

- 生成：建 ``tasks``（task_type=insight）→ Celery ``tasks.analyze_insights`` →
  ``InsightAnalysisAgent`` → 结果写 ``tasks.result``（不新建表，D-02）；
- 查询：最近一次完成的洞察任务（可按时间范围过滤）→ 结构化 InsightResponse；
- 无结果时返回空结构 ``status="empty"``（200，方便前端轮询）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_owner
from app.core.exceptions import DataSourceNotFoundError
from app.models import CleanedData, DataSource, Task, User
from app.schemas.insight import (
    InsightPainPoint,
    InsightRequest,
    InsightResponse,
    InsightTopQuestion,
)
from app.services import cleaning_service

INSIGHT_TASK_TYPE = "analyze"
MAX_DIALOGUES = 200


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_agent():  # noqa: ANN202 - 允许测试 monkeypatch
    from app.agents.insight_agent import InsightAnalysisAgent

    return InsightAnalysisAgent()


def enqueue_insight(task: Task) -> str:
    from app.tasks.insight import analyze_insights_task

    return str(analyze_insights_task.delay(str(task.id)))


async def _datasource_or_404(
    session: AsyncSession, datasource_id: uuid.UUID, user: User
) -> DataSource:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)
    return datasource


def _parse_bound(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.combine(datetime.strptime(value, "%Y-%m-%d").date(), time())
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


async def create_insight_task(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    request: InsightRequest,
) -> Task:
    await cleaning_service.ensure_no_running_task(
        session, datasource_id=datasource_id, task_type=INSIGHT_TASK_TYPE
    )
    task = Task(
        task_type=INSIGHT_TASK_TYPE,
        task_name="洞察分析",
        datasource_id=datasource_id,
        user_id=user.id,
        params=request.model_dump(),
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def _load_dialogues(
    session: AsyncSession,
    datasource_id: uuid.UUID,
    time_range: dict[str, str] | None,
) -> list[dict[str, Any]]:
    stmt = select(CleanedData).where(CleanedData.datasource_id == datasource_id)
    if time_range:
        start = _parse_bound(time_range.get("start"))
        end = _parse_bound(time_range.get("end"))
        if start is not None:
            stmt = stmt.where(CleanedData.timestamp >= start)
        if end is not None:
            stmt = stmt.where(CleanedData.timestamp <= end)
    stmt = stmt.order_by(CleanedData.timestamp.asc()).limit(MAX_DIALOGUES)
    rows = list((await session.execute(stmt)).scalars().all())
    return [
        {
            "dialogue_id": str(row.dialogue_id),
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "user_message": row.user_message,
            "ai_response": row.ai_response,
        }
        for row in rows
    ]


async def _execute_insight(
    task_id: uuid.UUID, session: AsyncSession, *, commit: bool
) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        return {"status": "missing", "task_id": str(task_id)}
    if task.status == "cancelled":
        return {"status": "cancelled", "task_id": str(task_id)}

    task.status = "running"
    task.started_at = _now_naive()
    task.progress = 10
    task.current_step = "loading_cleaned_data"
    await session.flush()

    try:
        params = task.params or {}
        dialogues = await _load_dialogues(session, task.datasource_id, params.get("time_range"))
        if not dialogues:
            raise ValueError("no cleaned data for insight analysis")

        agent = _build_agent()
        result = await agent.analyze(
            {
                "datasource_id": str(task.datasource_id),
                "dialogues": dialogues,
                "time_range": params.get("time_range"),
                "config": {
                    "analyze_sentiment": params.get("analyze_sentiment", True),
                    "identify_trends": params.get("identify_trends", True),
                    "find_pain_points": params.get("find_pain_points", True),
                },
            },
            session=session,
            task_id=task.id,
            user_id=task.user_id,
            datasource_id=task.datasource_id,
        )
        if not result.success or not result.data:
            raise RuntimeError("insight analysis failed: " + "; ".join(result.errors))

        task.status = "completed"
        task.progress = 100
        task.current_step = "completed"
        task.result = result.data
        task.completed_at = _now_naive()
        if task.started_at is not None:
            task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "completed", "task_id": str(task.id)}
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).error("insight task failed task={}", task.id)
        task.status = "failed"
        task.error_message = str(exc)[:1000]
        task.current_step = "failed"
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id), "error": str(exc)}


async def run_insight_task(task_id: str, *, session: AsyncSession | None = None) -> dict[str, Any]:
    if session is not None:
        return await _execute_insight(uuid.UUID(task_id), session, commit=False)

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        return await _execute_insight(uuid.UUID(task_id), db, commit=True)


async def get_latest_insights(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    start: str | None = None,
    end: str | None = None,
) -> InsightResponse:
    await _datasource_or_404(session, datasource_id, user)

    stmt = select(Task).where(
        Task.datasource_id == datasource_id,
        Task.task_type == INSIGHT_TASK_TYPE,
        Task.status == "completed",
    )
    start_at = _parse_bound(start)
    end_at = _parse_bound(end)
    if start_at is not None:
        stmt = stmt.where(Task.completed_at >= start_at)
    if end_at is not None:
        stmt = stmt.where(Task.completed_at <= end_at)
    task = await session.scalar(stmt.order_by(Task.completed_at.desc()).limit(1))

    if task is None or not task.result:
        return InsightResponse(datasource_id=datasource_id, status="empty")

    payload = task.result
    top_questions = [
        InsightTopQuestion(
            question=str(item.get("question", "")),
            frequency=int(item.get("count", item.get("frequency", 0)) or 0),
            category=item.get("category"),
        )
        for item in payload.get("top_questions") or []
    ]
    pain_points = [
        InsightPainPoint(
            issue=str(item.get("issue", "")),
            frequency=int(item.get("frequency", 0) or 0),
            severity=item.get("severity"),
            suggestions=item.get("suggestions"),
        )
        for item in payload.get("pain_points") or []
    ]
    return InsightResponse(
        datasource_id=datasource_id,
        status="completed",
        time_range=(task.params or {}).get("time_range"),
        intent_distribution=payload.get("intent_distribution") or {},
        top_questions=top_questions,
        sentiment_distribution=payload.get("sentiment_distribution") or {},
        sentiment_trend=payload.get("sentiment_trend") or [],
        pain_points=pain_points,
        unresolved_issues=payload.get("unresolved_issues") or [],
        emerging_topics=payload.get("emerging_topics") or [],
        seasonal_patterns=payload.get("seasonal_patterns"),
        degraded=bool(payload.get("degraded")),
        created_at=task.completed_at,
    )


__all__ = [
    "INSIGHT_TASK_TYPE",
    "create_insight_task",
    "enqueue_insight",
    "get_latest_insights",
    "run_insight_task",
]
