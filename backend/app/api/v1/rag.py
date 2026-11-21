"""RAG 执行与 Trace API（Phase 2）。

- ``POST /rag/queries``：执行一次检索/问答并落 trace（写权限）；
- ``GET /rag/traces``：Trace 列表（按任务/状态/适配器过滤）；
- ``GET /rag/traces/{trace_id}``：Trace 详情（上下文、配置快照、缺失字段、原始响应）；
- ``GET /rag/health``：适配器可用性探测（不返回密钥）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import pagination_params, require_roles
from app.core.database import get_db
from app.core.exceptions import RagTraceNotFoundError
from app.core.ownership import assert_owner
from app.core.pagination import PaginationParams
from app.models import RagTrace, User
from app.repositories import rag_trace as trace_repo
from app.schemas.base import Page
from app.schemas.rag import (
    RagAdapterHealth,
    RagContextRead,
    RagQueryRequest,
    RagTraceListItem,
    RagTraceRead,
)
from app.services.rag import build_adapter
from app.services.rag import execute as rag_execute

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")


def _context_to_read(item: dict) -> RagContextRead:
    return RagContextRead(
        document_id=item.get("document_id"),
        chunk_id=item.get("chunk_id"),
        title=item.get("title"),
        content=item.get("content") or "",
        score=item.get("score"),
        rank=item.get("rank"),
        metadata=item.get("metadata") or {},
    )


def _trace_to_read(trace: RagTrace) -> RagTraceRead:
    contexts = [_context_to_read(item) for item in trace.retrieved_contexts or []]
    return RagTraceRead(
        trace_id=trace.id,
        dataset_item_id=trace.dataset_item_id,
        task_id=trace.task_id,
        adapter=trace.adapter,
        execution_mode=trace.mode,
        context_source=trace.context_source,
        context_available=bool(contexts),
        external_session_id=trace.external_session_id,
        query=trace.query,
        answer=trace.answer,
        retrieved_contexts=contexts,
        retrieved_scores=[context.score for context in contexts],
        model_config_snapshot=dict(trace.model_config or {}),
        retrieval_config=dict(trace.retrieval_config or {}),
        prompt_snapshot=dict(trace.prompt_snapshot or {}),
        latency_ms=trace.latency_ms,
        token_usage=dict(trace.token_usage) if trace.token_usage else None,
        missing=list(trace.missing or []),
        execution_status=trace.status,
        error_message=trace.error_message,
        created_at=trace.created_at,
    )


async def _trace_or_404(session: AsyncSession, *, user: User, trace_id: uuid.UUID) -> RagTrace:
    trace = await trace_repo.get_trace(session, trace_id)
    if trace is None:
        raise RagTraceNotFoundError(details={"trace_id": str(trace_id)})
    assert_owner(trace.user_id, user)
    return trace


@router.post(
    "/queries",
    response_model=RagTraceRead,
    response_model_by_alias=False,
    status_code=status.HTTP_201_CREATED,
    summary="执行一次 RAG 查询并保存 trace",
)
async def run_query(
    payload: RagQueryRequest,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagTraceRead:
    query_text = payload.query
    if payload.dataset_item_id is not None:
        item = await rag_execute.load_item_for_user(
            session, user=user, dataset_item_id=payload.dataset_item_id
        )
        query_text = query_text or item.query
    assert query_text

    config = dict(payload.config or {})
    if payload.top_k is not None:
        config["top_k"] = payload.top_k

    adapter = build_adapter(payload.adapter)
    try:
        trace = await rag_execute.execute_query(
            session,
            user=user,
            adapter=adapter,
            query=query_text,
            mode=payload.mode,
            dataset_item_id=payload.dataset_item_id,
            config=config,
        )
    finally:
        await adapter.aclose()

    return _trace_to_read(trace)


@router.get(
    "/traces",
    response_model=Page[RagTraceListItem],
    response_model_by_alias=False,
    summary="Trace 列表（任务/状态/适配器过滤）",
)
async def list_traces(
    task_id: uuid.UUID | None = Query(default=None),
    dataset_item_id: uuid.UUID | None = Query(default=None),
    trace_status: str | None = Query(default=None, alias="status", max_length=20),
    adapter: str | None = Query(default=None, max_length=50),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[RagTraceListItem]:
    scope = None if user.role == "admin" else user.id
    rows, pagination = await trace_repo.list_traces(
        session,
        user_id=scope,
        task_id=task_id,
        dataset_item_id=dataset_item_id,
        status=trace_status,
        adapter=adapter,
        params=params,
    )
    items = [
        RagTraceListItem(
            trace_id=row.id,
            dataset_item_id=row.dataset_item_id,
            task_id=row.task_id,
            adapter=row.adapter,
            execution_mode=row.mode,
            context_source=row.context_source,
            context_available=bool(row.retrieved_contexts),
            query=row.query,
            execution_status=row.status,
            latency_ms=row.latency_ms,
            context_count=len(row.retrieved_contexts or []),
            missing=list(row.missing or []),
            created_at=row.created_at,
        )
        for row in rows
    ]
    return Page[RagTraceListItem](items=items, pagination=pagination)


@router.get(
    "/traces/{trace_id}",
    response_model=RagTraceRead,
    response_model_by_alias=False,
    summary="Trace 详情（含上下文 / 配置 / 缺失字段 / 原始响应）",
)
async def get_trace(
    trace_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagTraceRead:
    trace = await _trace_or_404(session, user=user, trace_id=trace_id)
    return _trace_to_read(trace)


@router.get(
    "/health",
    response_model=RagAdapterHealth,
    response_model_by_alias=False,
    summary="适配器可用性（不返回密钥）",
)
async def adapter_health(
    adapter: str | None = Query(default=None, max_length=50),
    user: User = Depends(require_roles(*READ_ROLES)),
) -> RagAdapterHealth:
    resolved = build_adapter(adapter, require_configured=False)
    configured = bool(getattr(resolved, "configured", True))
    missing_loader = getattr(resolved, "missing_settings", None)
    missing = list(missing_loader()) if callable(missing_loader) else []
    try:
        healthy = await resolved.health_check()
    finally:
        await resolved.aclose()
    return RagAdapterHealth(
        adapter=resolved.name, configured=configured, healthy=healthy, missing=missing
    )
