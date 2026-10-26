"""清洗编排与清洗结果服务（B-305 / B-314）。

职责：
- 重复任务护栏、创建 ``tasks`` 记录、入队 Celery、回写 ``celery_task_id``；
- ``run_clean_task``：真正执行清洗（DataCleaningAgent）→ 写 ``cleaned_data`` →
  推进 ``raw_data`` / ``datasource`` / ``task`` 状态；
- ``list_cleaned_data`` / ``get_cleaned_data``：清洗结果查询（API §6.3 / §6.4）。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.api.deps import assert_owner
from app.api.pagination import PaginationParams, paginate
from app.core.exceptions import (
    CleanedDataNotFoundError,
    DataSourceNotFoundError,
    TaskAlreadyRunningError,
)
from app.models import CleanedData, DataSource, RawData, Task, User
from app.schemas.agents.cleaning import CleaningConfig, CleaningInput
from app.schemas.base import Pagination

ACTIVE_STATUSES = ("pending", "running")
CLEAN_TASK_TYPE = "clean"
DIALOGUE_NAMESPACE = uuid.UUID("6f1a6d1e-2b7f-4c5e-9a10-3c2b1d4e5f60")

_CLEANED_SORTABLE: dict[str, InstrumentedAttribute] = {
    "timestamp": CleanedData.timestamp,
    "quality_score": CleanedData.quality_score,
    "created_at": CleanedData.created_at,
}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- 任务编排


async def count_pending_records(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(RawData)
            .where(
                RawData.datasource_id == datasource_id,
                RawData.status == "pending",
            )
        )
        or 0
    )


async def ensure_no_running_task(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    task_type: str = CLEAN_TASK_TYPE,
) -> None:
    """同数据源同类任务在跑 → 409 TASK_ALREADY_RUNNING。"""
    running = int(
        await session.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.datasource_id == datasource_id,
                Task.task_type == task_type,
                Task.status.in_(ACTIVE_STATUSES),
            )
        )
        or 0
    )
    if running:
        raise TaskAlreadyRunningError(
            details={"datasource_id": str(datasource_id), "task_type": task_type}
        )


async def create_clean_task(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    task_name: str,
    params: dict[str, Any],
) -> Task:
    task = Task(
        task_type=CLEAN_TASK_TYPE,
        task_name=task_name,
        datasource_id=datasource_id,
        user_id=user.id,
        params=params,
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


def enqueue_clean(task: Task) -> str:
    """提交 Celery 任务并返回 celery task id（测试可 monkeypatch）。"""
    from app.tasks.cleaning import clean_datasource

    result = clean_datasource.delay(str(task.id))
    return str(result.id)


def _build_agent():  # noqa: ANN202 - 允许测试 monkeypatch 返回替身
    from app.agents.cleaning_agent import DataCleaningAgent

    return DataCleaningAgent()


async def _load_raw_items(session: AsyncSession, task: Task) -> list[RawData]:
    params = task.params or {}
    raw_data_id = params.get("raw_data_id")
    if raw_data_id:
        item = await session.get(RawData, uuid.UUID(str(raw_data_id)))
        return [item] if item is not None else []

    data_ids = params.get("data_ids") or []
    if data_ids:
        stmt = select(RawData).where(RawData.id.in_([uuid.UUID(str(item)) for item in data_ids]))
        return list((await session.execute(stmt)).scalars().all())

    stmt = select(RawData).where(
        RawData.datasource_id == task.datasource_id,
        RawData.status == "pending",
    )
    return list((await session.execute(stmt)).scalars().all())


def _config_from_params(params: dict[str, Any]) -> CleaningConfig:
    raw = params.get("config") or {}
    allowed = set(CleaningConfig.model_fields)
    return CleaningConfig(**{k: v for k, v in raw.items() if k in allowed})


def _raw_text(raw: RawData) -> str:
    content = raw.raw_content or {}
    text = content.get("text")
    if text:
        return str(text)
    return json.dumps(content, ensure_ascii=False)


def _dialogue_uuid(raw_id: uuid.UUID, dialogue_id: str) -> uuid.UUID:
    return uuid.uuid5(DIALOGUE_NAMESPACE, f"{raw_id}:{dialogue_id}")


async def _persist_dialogues(
    session: AsyncSession,
    *,
    raw: RawData,
    result_data: dict[str, Any],
    agent_version: str,
    duration: float,
    token_usage: dict[str, int],
) -> tuple[int, float]:
    """写入 cleaned_data，返回 (条数, 质量分合计)。"""
    dialogues = result_data.get("dialogues") or []
    created = 0
    quality_total = 0.0
    for item in dialogues:
        dialogue_id = str(item.get("dialogue_id") or created + 1)
        timestamp = item.get("timestamp")
        parsed_ts: datetime | None = None
        if isinstance(timestamp, str):
            try:
                parsed_ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed_ts.tzinfo is not None:
                    parsed_ts = parsed_ts.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                parsed_ts = None
        score = float(item.get("quality_score") or 0)
        score = min(100.0, max(0.0, score))
        session.add(
            CleanedData(
                datasource_id=raw.datasource_id,
                raw_data_id=raw.id,
                dialogue_id=_dialogue_uuid(raw.id, dialogue_id),
                timestamp=parsed_ts or _now_naive(),
                user_message=str(item.get("user_message") or ""),
                ai_response=str(item.get("ai_response") or ""),
                metadata_={"agent": "cleaning_agent", "source_dialogue_id": dialogue_id},
                quality_score=score,
                issues=list(item.get("issues") or []),
                agent_version=agent_version,
                processing_duration=duration,
                token_usage=token_usage,
            )
        )
        created += 1
        quality_total += score
    return created, quality_total


async def _execute_clean(
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
    task.current_step = "loading_raw_data"
    await session.flush()

    cleaned_total = 0
    quality_total = 0.0
    raw_records = 0
    failed_raw = 0
    datasource: DataSource | None = None

    try:
        raw_items = await _load_raw_items(session, task)
        if not raw_items:
            raise ValueError("no raw data to clean")
        raw_records = len(raw_items)
        config = _config_from_params(task.params or {})

        for index, raw in enumerate(raw_items, start=1):
            agent = _build_agent()
            result = await agent.clean(
                CleaningInput(
                    datasource_id=raw.datasource_id,
                    raw_data=_raw_text(raw),
                    data_type=(raw.raw_content or {}).get("format") or "txt",
                    config=config,
                ).model_dump(mode="json"),
                session=session,
                task_id=task.id,
                user_id=task.user_id,
                datasource_id=raw.datasource_id,
            )

            if not result.success:
                failed_raw += 1
                raw.status = "failed"
                raw.error_message = "; ".join(result.errors)[:1000] or "cleaning failed"
                await session.flush()
                continue

            data = result.data or {}
            created, raw_quality = await _persist_dialogues(
                session,
                raw=raw,
                result_data=data,
                agent_version=str(result.metadata.get("version", "v1.0.0")),
                duration=result.duration,
                token_usage=result.token_usage,
            )
            cleaned_total += created
            quality_total += raw_quality
            raw.status = "completed"
            raw.processed_at = _now_naive()
            task.progress = min(90, 5 + int(index / raw_records * 85))
            task.current_step = f"cleaned {index}/{raw_records}"
            await session.flush()

        datasource = await session.get(DataSource, task.datasource_id)
        if datasource is not None and cleaned_total:
            statistics = dict(datasource.statistics or {})
            statistics.update(
                {
                    "total_records": int(statistics.get("total_records", 0)) + raw_records,
                    "cleaned_records": int(statistics.get("cleaned_records", 0)) + cleaned_total,
                    "quality_score_avg": round(quality_total / cleaned_total, 2),
                    "last_processed_at": _now_naive().isoformat(),
                }
            )
            datasource.statistics = statistics
            datasource.workflow_status = "data_cleaned"

        task.status = "completed" if cleaned_total else "failed"
        task.progress = 100
        task.current_step = "completed" if cleaned_total else "no_records_cleaned"
        task.completed_at = _now_naive()
        if task.started_at is not None:
            task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
        task.result = {
            "raw_records": raw_records,
            "failed_raw_records": failed_raw,
            "cleaned_records": cleaned_total,
        }
        if cleaned_total == 0:
            task.error_message = "no dialogues were cleaned"
        await session.flush()
        if commit:
            await session.commit()

        logger.info(
            "clean task done task={} datasource={} cleaned={}",
            task.id,
            task.datasource_id,
            cleaned_total,
        )
        return {
            "status": task.status,
            "task_id": str(task.id),
            "cleaned_records": cleaned_total,
        }

    except Exception as exc:  # noqa: BLE001 - 任务失败需落库
        logger.opt(exception=exc).error("clean task failed task={}", task.id)
        task.status = "failed"
        task.error_message = str(exc)[:1000]
        task.current_step = "failed"
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id), "error": str(exc)}


async def run_clean_task(task_id: str, *, session: AsyncSession | None = None) -> dict[str, Any]:
    """清洗执行入口：传入 ``session`` 时复用（测试），否则自建并提交。"""
    if session is not None:
        return await _execute_clean(uuid.UUID(task_id), session, commit=False)

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        result = await _execute_clean(uuid.UUID(task_id), db, commit=True)
    from app.core.database import dispose_engine

    await dispose_engine()
    return result


# --------------------------------------------------------------------------- 结果查询


async def list_cleaned_data(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    params: PaginationParams,
    quality_score_min: float | None = None,
    quality_score_max: float | None = None,
    has_issues: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[CleanedData], Pagination]:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)

    stmt = select(CleanedData).where(CleanedData.datasource_id == datasource_id)
    if quality_score_min is not None:
        stmt = stmt.where(CleanedData.quality_score >= quality_score_min)
    if quality_score_max is not None:
        stmt = stmt.where(CleanedData.quality_score <= quality_score_max)
    if has_issues is True:
        stmt = stmt.where(func.cardinality(CleanedData.issues) > 0)
    elif has_issues is False:
        stmt = stmt.where(
            (CleanedData.issues.is_(None)) | (func.cardinality(CleanedData.issues) == 0)
        )
    if date_from is not None:
        stmt = stmt.where(CleanedData.timestamp >= date_from)
    if date_to is not None:
        stmt = stmt.where(CleanedData.timestamp <= date_to)

    return await paginate(session, stmt, params, sortable=_CLEANED_SORTABLE)


async def get_cleaned_data(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    data_id: uuid.UUID,
) -> CleanedData:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)

    item = await session.get(CleanedData, data_id)
    if item is None or item.datasource_id != datasource_id:
        raise CleanedDataNotFoundError(details={"data_id": str(data_id)})
    return item


__all__ = [
    "ACTIVE_STATUSES",
    "CLEAN_TASK_TYPE",
    "count_pending_records",
    "create_clean_task",
    "enqueue_clean",
    "ensure_no_running_task",
    "get_cleaned_data",
    "list_cleaned_data",
    "run_clean_task",
]
