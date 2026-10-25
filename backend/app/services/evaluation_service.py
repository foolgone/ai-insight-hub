"""质量评估服务（B-403 / B-404；API 设计 §7）。

- 任务编排：重复任务护栏 → 建 task → Celery 入队（``tasks.evaluate_datasource``）；
- 执行：逐条 ``CleanedData`` 调用 ``QualityEvaluationAgent`` → 写 ``analysis_results``
  （``analysis_type="quality"``）→ 推进 task 状态；
- 查询：列表 + 汇总（平均分 / 需复核数 / 维度均分）；
- 复核：把结论写回 ``analysis_results.result.review``，不新建 review_queue（D-05）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_owner
from app.api.pagination import PaginationParams, paginate
from app.core.errors import FrameworkErrorCode
from app.core.exceptions import (
    AIInsightHubException,
    DataSourceNotFoundError,
)
from app.models import (
    AnalysisResult,
    CleanedData,
    DataSource,
    KnowledgeBase,
    Task,
    User,
)
from app.schemas.agents.evaluation import EvaluationConfig
from app.schemas.analysis import QualityAnalysisSummary
from app.schemas.base import Pagination
from app.services import cleaning_service

EVALUATE_TASK_TYPE = "evaluate"
MAX_ITEMS_PER_TASK = 100
_SORTABLE = {"created_at": AnalysisResult.created_at}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_agent():  # noqa: ANN202 - 允许测试 monkeypatch
    from app.agents.evaluation_agent import QualityEvaluationAgent

    return QualityEvaluationAgent()


def enqueue_evaluation(task: Task) -> str:
    from app.tasks.evaluation import evaluate_datasource

    return str(evaluate_datasource.delay(str(task.id)).id)


async def _datasource_or_404(
    session: AsyncSession, datasource_id: uuid.UUID, user: User
) -> DataSource:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)
    return datasource


async def create_evaluation_task(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    data_ids: list[uuid.UUID],
    config: EvaluationConfig,
) -> Task:
    await cleaning_service.ensure_no_running_task(
        session, datasource_id=datasource_id, task_type=EVALUATE_TASK_TYPE
    )
    task = Task(
        task_type=EVALUATE_TASK_TYPE,
        task_name="质量评估",
        datasource_id=datasource_id,
        user_id=user.id,
        params={
            "data_ids": [str(item) for item in data_ids],
            "config": config.model_dump(),
        },
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def _load_targets(session: AsyncSession, task: Task) -> list[CleanedData]:
    params = task.params or {}
    data_ids = params.get("data_ids") or []
    stmt = select(CleanedData).where(CleanedData.datasource_id == task.datasource_id)
    if data_ids:
        stmt = stmt.where(CleanedData.id.in_([uuid.UUID(str(item)) for item in data_ids]))
    stmt = stmt.order_by(CleanedData.created_at.asc()).limit(MAX_ITEMS_PER_TASK)
    return list((await session.execute(stmt)).scalars().all())


async def _knowledge_snippets(
    session: AsyncSession, datasource_id: uuid.UUID
) -> list[dict[str, str]]:
    stmt = (
        select(KnowledgeBase)
        .where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.status == "active",
        )
        .limit(5)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [{"question": row.question, "answer": row.answer} for row in rows]


def _config_from_params(params: dict[str, Any]) -> EvaluationConfig:
    raw = params.get("config") or {}
    allowed = set(EvaluationConfig.model_fields)
    return EvaluationConfig(**{k: v for k, v in raw.items() if k in allowed})


async def _execute_evaluation(
    task_id: uuid.UUID, session: AsyncSession, *, commit: bool
) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        return {"status": "missing", "task_id": str(task_id)}
    if task.status == "cancelled":
        return {"status": "cancelled", "task_id": str(task_id)}

    task.status = "running"
    task.started_at = _now_naive()
    task.progress = 5
    task.current_step = "loading_cleaned_data"
    await session.flush()

    evaluated = 0
    failed = 0
    needs_review = 0
    try:
        targets = await _load_targets(session, task)
        if not targets:
            raise ValueError("no cleaned data to evaluate")
        knowledge = await _knowledge_snippets(session, task.datasource_id)
        config = _config_from_params(task.params or {})

        for index, item in enumerate(targets, start=1):
            agent = _build_agent()
            result = await agent.evaluate(
                {
                    "dialogue": {
                        "dialogue_id": str(item.dialogue_id),
                        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                        "user_message": item.user_message,
                        "ai_response": item.ai_response,
                    },
                    "knowledge_base": knowledge,
                    "config": config.model_dump(),
                },
                session=session,
                task_id=task.id,
                user_id=task.user_id,
                datasource_id=task.datasource_id,
            )

            if not result.success or not result.data:
                failed += 1
                logger.warning(
                    "evaluation failed data={} errors={}",
                    item.id,
                    result.errors,
                )
                continue

            payload = result.data
            if payload.get("needs_review"):
                needs_review += 1
            session.add(
                AnalysisResult(
                    datasource_id=task.datasource_id,
                    data_id=item.id,
                    analysis_type="quality",
                    result=payload,
                    agent_name=str(result.metadata.get("agent", "evaluation_agent")),
                    agent_version=str(result.metadata.get("version", "v1.0.0")),
                    ai_model=str(result.metadata.get("model", "")) or None,
                    processing_duration=result.duration,
                    token_usage=result.token_usage,
                    cost=float(result.cost),
                )
            )
            evaluated += 1
            task.progress = min(95, 5 + int(index / len(targets) * 90))
            task.current_step = f"evaluated {index}/{len(targets)}"
            await session.flush()

        task.status = "completed" if evaluated else "failed"
        task.progress = 100
        task.current_step = "completed" if evaluated else "no_records_evaluated"
        task.completed_at = _now_naive()
        if task.started_at is not None:
            task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
        task.result = {
            "evaluated": evaluated,
            "failed": failed,
            "needs_review": needs_review,
            "total": len(targets),
        }
        if not evaluated:
            task.error_message = "no dialogues were evaluated"
        await session.flush()
        if commit:
            await session.commit()

        return {
            "status": task.status,
            "task_id": str(task.id),
            "evaluated": evaluated,
            "needs_review": needs_review,
        }
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).error("evaluation task failed task={}", task.id)
        task.status = "failed"
        task.error_message = str(exc)[:1000]
        task.current_step = "failed"
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id), "error": str(exc)}


async def run_evaluation_task(
    task_id: str, *, session: AsyncSession | None = None
) -> dict[str, Any]:
    if session is not None:
        return await _execute_evaluation(uuid.UUID(task_id), session, commit=False)

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        return await _execute_evaluation(uuid.UUID(task_id), db, commit=True)


# --------------------------------------------------------------------------- 查询 / 复核


async def list_analysis_results(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    params: PaginationParams,
) -> tuple[list[AnalysisResult], Pagination, QualityAnalysisSummary]:
    await _datasource_or_404(session, datasource_id, user)

    stmt = select(AnalysisResult).where(
        AnalysisResult.datasource_id == datasource_id,
        AnalysisResult.analysis_type == "quality",
    )
    rows, pagination = await paginate(session, stmt, params, sortable=_SORTABLE)

    overall = cast(AnalysisResult.result["overall_score"].astext, Float)
    summary_filters = [
        AnalysisResult.datasource_id == datasource_id,
        AnalysisResult.analysis_type == "quality",
    ]
    summary_row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.avg(overall), 0).label("avg_score"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                AnalysisResult.result["needs_review"].astext == "true",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("needs_review"),
                *[
                    func.coalesce(
                        func.avg(
                            cast(
                                AnalysisResult.result["dimensions"][dimension]["score"].astext,
                                Float,
                            )
                        ),
                        0,
                    ).label(f"avg_{dimension}")
                    for dimension in (
                        "accuracy",
                        "completeness",
                        "hallucination",
                        "tone",
                        "compliance",
                    )
                ],
            ).where(*summary_filters)
        )
    ).one()

    summary = QualityAnalysisSummary(
        total=int(summary_row.total or 0),
        avg_overall_score=round(float(summary_row.avg_score or 0), 2),
        needs_review_count=int(summary_row.needs_review or 0),
        dimension_averages={
            dimension: round(float(getattr(summary_row, f"avg_{dimension}") or 0), 2)
            for dimension in (
                "accuracy",
                "completeness",
                "hallucination",
                "tone",
                "compliance",
            )
        },
    )
    return rows, pagination, summary


async def review_analysis_result(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    result_id: uuid.UUID,
    decision: str,
    note: str | None,
    corrected_scores: dict[str, float] | None,
) -> AnalysisResult:
    await _datasource_or_404(session, datasource_id, user)

    row = await session.get(AnalysisResult, result_id)
    if row is None or row.datasource_id != datasource_id or row.analysis_type != "quality":
        raise AIInsightHubException(
            "Analysis result not found",
            code=FrameworkErrorCode.HTTP_ERROR,
            status_code=404,
        )

    from app.agents.evaluation_agent import compute_overall_score
    from app.schemas.agents.evaluation import DIMENSION_WEIGHTS

    payload = dict(row.result or {})
    if corrected_scores:
        dimensions = dict(payload.get("dimensions") or {})
        for dimension, score in corrected_scores.items():
            if dimension not in DIMENSION_WEIGHTS:
                continue
            bounded = min(100.0, max(0.0, float(score)))
            dimensions[dimension] = {
                **(dimensions.get(dimension) or {}),
                "score": bounded,
            }
        payload["dimensions"] = dimensions
        enabled = [item for item in dimensions if item in DIMENSION_WEIGHTS]
        payload["overall_score"] = compute_overall_score(
            {item: float((dimensions[item] or {}).get("score", 0)) for item in enabled},
            enabled,
        )

    payload["needs_review"] = False
    payload["review"] = {
        "decision": decision,
        "note": note,
        "reviewer_id": str(user.id),
        "reviewed_at": _now_naive().isoformat(),
    }
    row.result = payload
    await session.flush()
    await session.refresh(row)
    return row


__all__ = [
    "EVALUATE_TASK_TYPE",
    "create_evaluation_task",
    "enqueue_evaluation",
    "list_analysis_results",
    "review_analysis_result",
    "run_evaluation_task",
]
