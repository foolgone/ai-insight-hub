"""周报摘要（#5）：汇总最近 7 天的运行与成本，通过 SMTP 发送。

默认关闭（``WEEKLY_DIGEST_ENABLED=false``）；开启且配置 SMTP 后，
Celery beat 每周一 09:00 执行。没有 SMTP 时只写日志，不发邮件。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import func, select

from app.core.celery import celery_app
from app.core.config import settings
from app.models import KnowledgeGap, LlmCall, Task
from app.services import notification_service

DIGEST_DAYS = 7


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def render_digest(payload: dict[str, Any]) -> str:
    """纯文本周报正文（便于单测断言格式）。"""
    lines = [
        f"AI Insight Hub 周报（{payload['since']:%Y-%m-%d} ~ {payload['until']:%Y-%m-%d}）",
        "",
        "【任务】",
        f"  完成：{payload['tasks_completed']}    失败：{payload['tasks_failed']}",
    ]
    if payload["by_type"]:
        detail = "、".join(f"{name} {count}" for name, count in payload["by_type"].items())
        lines.append(f"  按类型：{detail}")
    lines.extend(
        [
            "",
            "【成本】",
            f"  服务端 Key 调用成本：${payload['cost']:.4f}（{payload['calls']} 次调用）",
            "",
            "【知识】",
            f"  待处理盲区：{payload['open_gaps']} 条",
            "",
            "—— 自动发送；如需关闭，设置 WEEKLY_DIGEST_ENABLED=false",
        ]
    )
    return "\n".join(lines)


async def collect_digest(session) -> dict[str, Any]:  # noqa: ANN001 - AsyncSession
    """汇总最近 7 天的任务 / 成本 / 盲区。只统计服务端 Key 的成本（BYOK 不计预算）。"""
    until = _now_naive()
    since = until - timedelta(days=DIGEST_DAYS)

    rows = (
        await session.execute(
            select(Task.task_type, Task.status, func.count())
            .where(Task.created_at >= since)
            .group_by(Task.task_type, Task.status)
        )
    ).all()
    completed = sum(count for _, status, count in rows if status == "completed")
    failed = sum(count for _, status, count in rows if status == "failed")
    by_type: dict[str, int] = {}
    for task_type, status, count in rows:
        if status == "completed":
            by_type[str(task_type)] = by_type.get(str(task_type), 0) + int(count)

    cost_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(LlmCall.total_cost), 0),
                func.count(),
            ).where(LlmCall.created_at >= since, LlmCall.key_source == "server")
        )
    ).one()
    open_gaps = int(
        await session.scalar(
            select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.status == "open")
        )
        or 0
    )
    return {
        "since": since,
        "until": until,
        "tasks_completed": completed,
        "tasks_failed": failed,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "cost": float(cost_row[0] or 0),
        "calls": int(cost_row[1] or 0),
        "open_gaps": open_gaps,
    }


@celery_app.task(name="tasks.weekly_digest")
def weekly_digest() -> dict[str, Any]:
    """每周一 09:00：发一封运营周报（未开启/未配置 SMTP 时只写日志）。"""
    if not settings.WEEKLY_DIGEST_ENABLED:
        logger.info("周报未开启（WEEKLY_DIGEST_ENABLED=false），跳过")
        return {"status": "disabled"}

    async def _run() -> dict[str, Any]:
        from app.core.database import SessionLocal, dispose_engine

        async with SessionLocal() as session:
            payload = await collect_digest(session)
        await dispose_engine()
        return payload

    payload = asyncio.run(_run())
    body = render_digest(payload)
    sent = notification_service.send_email(
        f"AI Insight Hub 周报（{payload['since']:%m-%d} ~ {payload['until']:%m-%d}）",
        body,
        to=settings.WEEKLY_DIGEST_TO or None,
    )
    logger.info("weekly digest done sent={} summary={}", sent, payload)
    return {"status": "sent" if sent else "no_smtp", **payload}


__all__ = ["collect_digest", "render_digest", "weekly_digest"]
