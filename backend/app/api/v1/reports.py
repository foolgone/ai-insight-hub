"""报告 API（API 设计 §9：B-509）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.pagination import PaginationParams
from app.core.database import get_db
from app.models import User
from app.schemas.base import Page
from app.schemas.report import (
    ReportCreate,
    ReportCreateResponse,
    ReportDetail,
    ReportItem,
)
from app.services import report_service

datasource_router = APIRouter()
router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")


@datasource_router.post(
    "/{datasource_id}/reports",
    response_model=ReportCreateResponse,
    response_model_by_alias=False,
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成报告（202）",
)
async def create_report(
    datasource_id: uuid.UUID,
    payload: ReportCreate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> ReportCreateResponse:
    report = await report_service.create_report(
        session,
        user=user,
        datasource_id=datasource_id,
        title=payload.title,
        report_type=payload.report_type,
        format=payload.format,
        config=payload.config,
    )
    # Celery 任务 id 由 tasks 表跟踪；Report 模型无 celery_task_id 列，不写幽灵属性
    report_service.enqueue_report(report)
    await session.flush()
    await session.refresh(report)
    return ReportCreateResponse(
        id=report.id,
        title=report.title,
        report_type=report.report_type,
        format=report.format,
        status=report.status,
        created_at=report.created_at,
    )


@datasource_router.get(
    "/{datasource_id}/reports",
    response_model=Page[ReportItem],
    response_model_by_alias=False,
    summary="报告列表（类型/状态过滤 + 分页）",
)
async def list_reports(
    datasource_id: uuid.UUID,
    params: PaginationParams = Depends(),
    report_type: str | None = None,
    status: str | None = None,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[ReportItem]:
    rows, pagination = await report_service.list_reports(
        session,
        user=user,
        datasource_id=datasource_id,
        params=params,
        report_type=report_type,
        status=status,
    )
    return Page[ReportItem](
        items=[ReportItem.model_validate(item) for item in rows],
        pagination=pagination,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetail,
    response_model_by_alias=False,
    summary="报告详情（累加浏览数）",
)
async def get_report(
    report_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> ReportDetail:
    report = await report_service.get_report(session, user=user, report_id=report_id)
    return ReportDetail.model_validate(report)


@router.get(
    "/{report_id}/download",
    summary="下载报告（文件流；累加下载数）",
)
async def download_report(
    report_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Response:
    filename, media_type, content = await report_service.download_report(
        session, user=user, report_id=report_id
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除报告（204）",
)
async def delete_report(
    report_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await report_service.delete_report(session, user=user, report_id=report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["datasource_router", "router"]
