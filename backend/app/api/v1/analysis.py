"""质量评估 API（API 设计 §7：B-403/B-404）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_llm_credential, require_roles
from app.api.pagination import PaginationParams
from app.core.database import get_db
from app.models import User
from app.schemas.agents.evaluation import EvaluationConfig
from app.schemas.analysis import (
    EvaluationRequest,
    EvaluationTaskResponse,
    QualityAnalysisItem,
    QualityAnalysisListResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.schemas.insight import (
    InsightRequest,
    InsightResponse,
    InsightTaskResponse,
)
from app.services import evaluation_service, insight_service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")

SECONDS_PER_RECORD = 3.0
MAX_ESTIMATED_RECORDS = 100


@router.post(
    "/{datasource_id}/analyze/quality",
    response_model=EvaluationTaskResponse,
    response_model_by_alias=False,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交质量评估任务（202）",
    dependencies=[Depends(require_llm_credential)],
)
async def analyze_quality(
    datasource_id: uuid.UUID,
    payload: EvaluationRequest | None = None,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> EvaluationTaskResponse:
    datasource = await evaluation_service._datasource_or_404(  # noqa: SLF001
        session, datasource_id, user
    )
    request = payload or EvaluationRequest()
    config = request.config if request.config else EvaluationConfig()

    record_count = len(request.data_ids) or MAX_ESTIMATED_RECORDS
    estimated_duration = max(5.0, round(record_count * SECONDS_PER_RECORD, 1))

    task = await evaluation_service.create_evaluation_task(
        session,
        user=user,
        datasource_id=datasource.id,
        data_ids=request.data_ids,
        config=config,
    )
    task.celery_task_id = evaluation_service.enqueue_evaluation(task)
    await session.flush()
    await session.refresh(task)

    return EvaluationTaskResponse(
        task_id=task.id,
        estimated_duration=estimated_duration,
        message="Quality evaluation task queued",
    )


@router.get(
    "/{datasource_id}/analysis/quality",
    response_model=QualityAnalysisListResponse,
    response_model_by_alias=False,
    summary="质量评估结果列表（分页 + 汇总）",
)
async def list_quality_analysis(
    datasource_id: uuid.UUID,
    params: PaginationParams = Depends(),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> QualityAnalysisListResponse:
    rows, pagination, summary = await evaluation_service.list_analysis_results(
        session, user=user, datasource_id=datasource_id, params=params
    )
    items = []
    for row in rows:
        payload = row.result or {}
        items.append(
            QualityAnalysisItem(
                id=row.id,
                data_id=row.data_id,
                overall_score=float(payload.get("overall_score") or 0),
                needs_review=bool(payload.get("needs_review")),
                quality_level=payload.get("quality_level"),
                dimensions=payload.get("dimensions") or {},
                agent_name=row.agent_name,
                agent_version=row.agent_version,
                created_at=row.created_at,
            )
        )
    return QualityAnalysisListResponse(items=items, pagination=pagination, summary=summary)


@router.post(
    "/{datasource_id}/analysis/quality/{result_id}/review",
    response_model=ReviewResponse,
    response_model_by_alias=False,
    summary="人工复核（结论回写 analysis_results）",
)
async def review_quality_analysis(
    datasource_id: uuid.UUID,
    result_id: uuid.UUID,
    payload: ReviewRequest,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    row = await evaluation_service.review_analysis_result(
        session,
        user=user,
        datasource_id=datasource_id,
        result_id=result_id,
        decision=payload.decision,
        note=payload.note,
        corrected_scores=payload.corrected_scores,
    )
    return ReviewResponse(
        id=row.id,
        needs_review=False,
        decision=payload.decision,
        message="Review recorded",
    )


@router.post(
    "/{datasource_id}/analyze/insights",
    response_model=InsightTaskResponse,
    response_model_by_alias=False,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交洞察分析任务（202）",
    dependencies=[Depends(require_llm_credential)],
)
async def analyze_insights(
    datasource_id: uuid.UUID,
    payload: InsightRequest | None = None,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> InsightTaskResponse:
    datasource = await insight_service._datasource_or_404(  # noqa: SLF001
        session, datasource_id, user
    )
    request = payload or InsightRequest()
    task = await insight_service.create_insight_task(
        session, user=user, datasource_id=datasource.id, request=request
    )
    task.celery_task_id = insight_service.enqueue_insight(task)
    await session.flush()
    await session.refresh(task)
    return InsightTaskResponse(task_id=task.id, status="pending")


@router.get(
    "/{datasource_id}/analysis/insights",
    response_model=InsightResponse,
    response_model_by_alias=False,
    summary="获取洞察结果（最近一次完成的任务）",
)
async def get_insights(
    datasource_id: uuid.UUID,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> InsightResponse:
    return await insight_service.get_latest_insights(
        session,
        user=user,
        datasource_id=datasource_id,
        start=start,
        end=end,
    )


__all__ = ["router"]
