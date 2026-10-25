"""成本监控与告警任务（B-608；成本管理 §5 / 可观测文档）。

- 每日汇总 ``llm_calls`` 成功调用成本（UTC 日界）；
- 按 ``DAILY_COST_LIMIT`` 计算使用率，命中阈值时记录 warning 日志（供日志告警采集）；
- Celery beat 每天 00:05（Asia/Shanghai）触发 ``tasks.monitor_cost``；
- 对账口径：成本只认 ``llm_calls`` 聚合，不读进程内 Prometheus 指标。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery import celery_app
from app.core.config import settings
from app.core.cost_alerts import CostAlertManager
from app.core.degradation import level_for_ratio
from app.models import LlmCall


async def _collect(session: AsyncSession) -> dict[str, Any]:
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    total = (
        await session.scalar(
            select(func.coalesce(func.sum(LlmCall.total_cost), 0)).where(
                LlmCall.status == "success",
                LlmCall.created_at >= start,
            )
        )
        or 0
    )
    total_cost = Decimal(str(total))
    limit = float(settings.DAILY_COST_LIMIT)
    ratio = float(total_cost) / limit if limit > 0 else 0.0
    level = level_for_ratio(ratio)
    alert = CostAlertManager.should_notify(level)

    if alert:
        logger.warning(
            "cost alert level={} usage={:.2f}% total_cost={} daily_limit={}",
            level.value,
            ratio * 100,
            total_cost,
            limit,
        )
    else:
        logger.info(
            "cost monitor usage={:.2f}% total_cost={} daily_limit={}",
            ratio * 100,
            total_cost,
            limit,
        )
    return {
        "date": start.date().isoformat(),
        "total_cost": str(total_cost),
        "daily_limit": limit,
        "ratio": round(ratio, 4),
        "level": level.value,
        "alert": alert,
    }


async def run_cost_monitor(
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """执行一次成本对账（可注入 session 便于测试）。"""
    if session is not None:
        return await _collect(session)

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        return await _collect(db)


@celery_app.task(name="tasks.monitor_cost")
def monitor_cost_task() -> dict[str, Any]:
    return asyncio.run(run_cost_monitor())


__all__ = ["monitor_cost_task", "run_cost_monitor"]
