"""RAG 批量评测 Celery 任务（Phase 3C）。"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.core.celery import celery_app


@celery_app.task(
    name="tasks.rag_evaluation",
    acks_late=True,
    reject_on_worker_lost=True,
)
def rag_evaluation(run_id: str) -> dict[str, Any]:
    """执行一次评测 Run（幂等：重复投递由 advisory lock + 唯一键兜底）。"""
    from app.services.rag_evaluation_runner import run_rag_evaluation

    return asyncio.run(run_rag_evaluation(run_id))


@celery_app.task(name="tasks.recover_stale_rag_runs")
def recover_stale_rag_runs() -> dict[str, Any]:
    """识别心跳超时的评测 Run，标记 failed(stale_worker) 供用户重试。"""

    async def _run() -> int:
        from app.core.database import SessionLocal, dispose_engine
        from app.services import rag_evaluation_service

        async with SessionLocal() as session:
            count = await rag_evaluation_service.recover_stale_runs(session)
            await session.commit()
        await dispose_engine()
        return count

    stale = asyncio.run(_run())
    if stale:
        logger.warning("recovered stale rag evaluation runs count={}", stale)
    return {"stale_runs": stale}


__all__ = ["rag_evaluation", "recover_stale_rag_runs"]
