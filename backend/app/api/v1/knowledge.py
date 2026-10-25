"""知识库 API（API 设计 §8：B-506）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.pagination import PaginationParams
from app.core.database import get_db
from app.models import User
from app.schemas.base import Page
from app.schemas.knowledge import (
    FAQCreate,
    FAQItem,
    FAQUpdate,
    GapsResponse,
    KnowledgeExtractionRequest,
    KnowledgeExtractionResponse,
    SearchResponse,
)
from app.services import knowledge_service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")


@router.post(
    "/{datasource_id}/extract-knowledge",
    response_model=KnowledgeExtractionResponse,
    response_model_by_alias=False,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交知识提取任务（202）",
)
async def extract_knowledge(
    datasource_id: uuid.UUID,
    payload: KnowledgeExtractionRequest | None = None,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> KnowledgeExtractionResponse:
    datasource = await knowledge_service._datasource_or_404(  # noqa: SLF001
        session, datasource_id, user
    )
    request = payload or KnowledgeExtractionRequest()
    task = await knowledge_service.create_extraction_task(
        session, user=user, datasource_id=datasource.id, request=request
    )
    task.celery_task_id = knowledge_service.enqueue_extract(task)
    await session.flush()
    await session.refresh(task)
    return KnowledgeExtractionResponse(task_id=task.id, status="pending")


@router.get(
    "/{datasource_id}/knowledge/faq",
    response_model=Page[FAQItem],
    response_model_by_alias=False,
    summary="FAQ 列表（分类/频次过滤 + 分页）",
)
async def list_faqs(
    datasource_id: uuid.UUID,
    params: PaginationParams = Depends(),
    category: str | None = Query(default=None),
    min_frequency: int | None = Query(default=None, ge=1),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[FAQItem]:
    rows, pagination = await knowledge_service.list_faqs(
        session,
        user=user,
        datasource_id=datasource_id,
        params=params,
        category=category,
        min_frequency=min_frequency,
    )
    return Page[FAQItem](
        items=[FAQItem.model_validate(item) for item in rows],
        pagination=pagination,
    )


@router.get(
    "/{datasource_id}/knowledge/search",
    response_model=SearchResponse,
    response_model_by_alias=False,
    summary="知识检索（pg_trgm + 向量混合）",
)
async def search_knowledge(
    datasource_id: uuid.UUID,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
    threshold: float = Query(default=0.3, ge=0.0, le=1.0),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> SearchResponse:
    return await knowledge_service.search_faqs(
        session,
        user=user,
        datasource_id=datasource_id,
        query=q,
        limit=limit,
        threshold=threshold,
    )


@router.get(
    "/{datasource_id}/knowledge/gaps",
    response_model=GapsResponse,
    response_model_by_alias=False,
    summary="知识盲区（最近一次提取结果）",
)
async def list_gaps(
    datasource_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> GapsResponse:
    return await knowledge_service.list_gaps(session, user=user, datasource_id=datasource_id)


@router.post(
    "/{datasource_id}/knowledge/faq",
    response_model=FAQItem,
    response_model_by_alias=False,
    status_code=status.HTTP_201_CREATED,
    summary="手动创建 FAQ",
)
async def create_faq(
    datasource_id: uuid.UUID,
    payload: FAQCreate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> FAQItem:
    faq = await knowledge_service.create_faq(
        session, user=user, datasource_id=datasource_id, payload=payload
    )
    return FAQItem.model_validate(faq)


@router.patch(
    "/{datasource_id}/knowledge/faq/{faq_id}",
    response_model=FAQItem,
    response_model_by_alias=False,
    summary="更新 FAQ",
)
async def update_faq(
    datasource_id: uuid.UUID,
    faq_id: uuid.UUID,
    payload: FAQUpdate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> FAQItem:
    faq = await knowledge_service.update_faq(
        session,
        user=user,
        datasource_id=datasource_id,
        faq_id=faq_id,
        payload=payload,
    )
    return FAQItem.model_validate(faq)


@router.delete(
    "/{datasource_id}/knowledge/faq/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 FAQ（204）",
)
async def delete_faq(
    datasource_id: uuid.UUID,
    faq_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await knowledge_service.delete_faq(
        session, user=user, datasource_id=datasource_id, faq_id=faq_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
