"""执行一次 RAG 查询并落库（Phase 2）。

职责：
1. 调适配器（``retrieve`` / ``query``），失败也落 trace（status=failed + 错误原文）；
2. 把结果写成 ``rag_traces``（含上下文、配置快照、缺失字段、原始响应）。

不做：指标计算、judge 调用（Phase 3）。
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import QaDatasetNotFoundError
from app.core.ownership import assert_owner
from app.models import QaDatasetItem, RagTrace, User
from app.ports.rag import RAGMode, RAGPort, RAGResult, RetrievedContext
from app.repositories import qa_dataset as qa_repo
from app.repositories import rag_trace as trace_repo


def _context_payload(context: RetrievedContext) -> dict[str, Any]:
    return {
        "document_id": context.document_id,
        "chunk_id": context.chunk_id,
        "title": context.title,
        "content": context.content,
        "score": context.score,
        "rank": context.rank,
        "metadata": dict(context.metadata or {}),
    }


async def load_item_for_user(
    session: AsyncSession, *, user: User, dataset_item_id: uuid.UUID
) -> QaDatasetItem:
    """校验条目归属（item → version → dataset → user）。"""
    item = await qa_repo.get_item(session, dataset_item_id)
    if item is None:
        raise QaDatasetNotFoundError(details={"item_id": str(dataset_item_id)})
    version = await qa_repo.get_version(session, item.version_id)
    if version is None:
        raise QaDatasetNotFoundError(details={"version_id": str(item.version_id)})
    dataset = await qa_repo.get_dataset(session, version.dataset_id)
    if dataset is None:
        raise QaDatasetNotFoundError(details={"dataset_id": str(version.dataset_id)})
    assert_owner(dataset.user_id, user)
    return item


async def execute_query(
    session: AsyncSession,
    *,
    user: User,
    adapter: RAGPort,
    query: str,
    mode: RAGMode,
    dataset_item_id: uuid.UUID | None = None,
    config: Mapping[str, Any] | None = None,
    task_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> RagTrace:
    """执行一次查询并返回 trace；同一幂等键重复调用返回既有 trace。"""
    if dataset_item_id is not None:
        await load_item_for_user(session, user=user, dataset_item_id=dataset_item_id)

    if idempotency_key:
        existing = await trace_repo.get_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            logger.info("rag trace idempotent hit key={} trace={}", idempotency_key, existing.id)
            return existing

    started = time.perf_counter()
    result: RAGResult | None = None
    error: str | None = None
    try:
        if mode == "retrieve":
            result = await adapter.retrieve(query, config=config)
        else:
            result = await adapter.query(query, config=config)
    except Exception as exc:  # noqa: BLE001 - 外部失败必须落 trace，不能吞
        error = f"{type(exc).__name__}: {exc}"[:2000]
        logger.warning("rag adapter failed adapter={} mode={} error={}", adapter.name, mode, error)

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if result is not None:
        trace = RagTrace(
            user_id=user.id,
            dataset_item_id=dataset_item_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            adapter=adapter.name,
            mode=result.mode,
            context_source=result.context_source,
            external_session_id=result.external_session_id,
            query=result.query,
            answer=result.answer,
            retrieved_contexts=[_context_payload(item) for item in result.contexts],
            raw_response=result.raw,
            model_config=dict(result.model_config or {}),
            retrieval_config=dict(result.retrieval_config or {}),
            prompt_snapshot=dict(result.prompt_snapshot or {}),
            latency_ms=result.latency_ms,
            token_usage=dict(result.token_usage) if result.token_usage else None,
            missing=list(result.missing),
            status="success",
            error_message=None,
        )
    else:
        trace = RagTrace(
            user_id=user.id,
            dataset_item_id=dataset_item_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            adapter=adapter.name,
            mode=mode,
            context_source="none",
            query=query,
            answer=None,
            retrieved_contexts=[],
            raw_response=None,
            model_config={},
            retrieval_config=dict(config or {}),
            prompt_snapshot={},
            latency_ms=elapsed_ms,
            token_usage=None,
            missing=["retrieved_contexts", "token_usage"],
            status="failed",
            error_message=error,
        )

    # 请求配置指纹：Trace 复用的唯一比较基准（含 KB / Agent / Tenant / top_k）。
    # 适配器回显（match_count 等）与请求配置形状不同，不能直接比较。
    trace.retrieval_config = {
        **dict(trace.retrieval_config or {}),
        "_request_config": dict(config or {}),
    }

    await trace_repo.add_trace(session, trace)
    logger.info(
        "rag trace recorded id={} adapter={} mode={} status={} contexts={} latency_ms={}",
        trace.id,
        trace.adapter,
        trace.mode,
        trace.status,
        len(trace.retrieved_contexts or []),
        trace.latency_ms,
    )
    return trace


def context_available(trace: RagTrace) -> bool:
    """本次执行是否真的拿到了上下文（用于前端/指标显式判断，不靠长度猜）。"""
    return bool(trace.retrieved_contexts)


__all__ = ["context_available", "execute_query", "load_item_for_user"]
