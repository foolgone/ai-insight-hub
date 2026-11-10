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
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.ownership import assert_owner
from app.core.pagination import PaginationParams, paginate
from app.core.exceptions import (
    CleanedDataNotFoundError,
    DataSourceNotFoundError,
    TaskAlreadyRunningError,
)
from app.application import media_pipeline, structure_service, task_control
from app.models import CleanedData, DataSource, RawData, Task, User
from app.schemas.agents.cleaning import CleaningConfig, CleaningInput, CleaningState
from app.schemas.base import Pagination
from app.services import parsers, storage_service

ACTIVE_STATUSES = ("pending", "running")
CLEAN_TASK_TYPE = "clean"
DIALOGUE_NAMESPACE = uuid.UUID("6f1a6d1e-2b7f-4c5e-9a10-3c2b1d4e5f60")
# 近似重复检测是 O(n²) 文本比较，超过该条数跳过（避免大文件把任务拖死）
NEAR_DUP_MAX_ITEMS = 2000

# 清洗状态机：6 态 + 失败，逐条记录循环（VALIDATING 后可回到下一条的 NORMALIZING）
_ALLOWED_TRANSITIONS: dict[CleaningState, set[CleaningState]] = {
    CleaningState.PENDING: {CleaningState.PARSING, CleaningState.FAILED},
    CleaningState.PARSING: {CleaningState.NORMALIZING, CleaningState.FAILED},
    CleaningState.NORMALIZING: {
        CleaningState.DEDUPLICATING,
        CleaningState.VALIDATING,  # 抽取失败时跳过去重，直接进入校验
        CleaningState.FAILED,
    },
    CleaningState.DEDUPLICATING: {CleaningState.VALIDATING, CleaningState.FAILED},
    CleaningState.VALIDATING: {
        CleaningState.NORMALIZING,
        CleaningState.COMPLETED,
        CleaningState.FAILED,
    },
    CleaningState.COMPLETED: set(),
    CleaningState.FAILED: set(),
}

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
    """取交给清洗 Agent 的文本：原文优先，其次逐行记录，最后退化为元数据 JSON。"""
    content = raw.raw_content or {}
    text = content.get("text")
    if text:
        return str(text)
    records = content.get("records")
    if records:
        return json.dumps(records, ensure_ascii=False, default=str)
    return json.dumps(content, ensure_ascii=False, default=str)


def _read_full_upload(raw: RawData) -> str | None:
    """入库文本被截断时，按 file_info.object_name 从对象存储读原文重新解析（P1-1）。"""
    file_info = raw.file_info or {}
    object_name = file_info.get("object_name")
    if not object_name:
        return None
    try:
        content = storage_service.read_upload(object_name, backend=file_info.get("storage_backend"))
        parsed = parsers.parse_upload(content, file_info.get("filename") or "upload.bin")
        return parsed.raw_text
    except Exception as exc:  # noqa: BLE001 - 存储不可用/文件缺失时回退入库文本
        logger.warning("read full upload failed raw={} error={}", raw.id, exc)
        return None


def _load_raw_text(raw: RawData) -> str:
    """优先返回完整文本：入库文本被截断时从对象存储读取（P1-1）。"""
    content = raw.raw_content or {}
    if content.get("truncated"):
        full_text = _read_full_upload(raw)
        if full_text:
            return full_text
    return _raw_text(raw)


def _dialogue_uuid(raw_id: uuid.UUID, dialogue_id: str) -> uuid.UUID:
    return uuid.uuid5(DIALOGUE_NAMESPACE, f"{raw_id}:{dialogue_id}")


# --------------------------------------------------------------------------- 状态机


def _current_state(task: Task) -> CleaningState | None:
    """从 ``current_step`` 前缀解析当前状态（兼容历史值如 ``loading_raw_data``）。"""
    prefix = (task.current_step or "").split(" ", 1)[0]
    try:
        return CleaningState(prefix)
    except ValueError:
        return None


def _advance_state(task: Task, state: CleaningState, *, detail: str | None = None) -> None:
    """推进清洗状态机；非法跳转直接抛错（防止状态回退/越级）。"""
    current = _current_state(task)
    if current is not None and state not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"illegal cleaning state transition: {current.value} -> {state.value}")
    task.current_step = f"{state.value} {detail}" if detail else state.value


# --------------------------------------------------------------------------- 去重


def _mark_near_duplicates(dialogues: list[dict[str, Any]], *, threshold: float) -> int:
    """标记近似重复对话（相似度 ≥ threshold），返回新增标记条数。

    策略：**保留记录、只打 ``duplicate`` 标签**——清洗阶段不删数据（宁低分不丢弃），
    下游知识提取还有一层精确去重（``knowledge_dedup.dedupe_dialogues``）。
    """
    if len(dialogues) < 2:
        return 0
    if len(dialogues) > NEAR_DUP_MAX_ITEMS:
        logger.warning(
            "skip near-duplicate detection: too many dialogues={} limit={}",
            len(dialogues),
            NEAR_DUP_MAX_ITEMS,
        )
        return 0

    from app.agents.tools import cleaning_tools

    pairs = cleaning_tools.detect_duplicates(dialogues, threshold=threshold)
    marked = 0
    for _first, duplicate in pairs:
        item = dialogues[duplicate]
        issues = item.setdefault("issues", [])
        if "duplicate" not in issues:
            issues.append("duplicate")
            marked += 1
    return marked


def _parse_timestamp(value: Any) -> datetime | None:
    """解析对话时间戳；缺失/非法返回 None（不伪造当前时间，P1-6）。"""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


async def _persist_dialogues(
    session: AsyncSession,
    *,
    raw: RawData,
    result_data: dict[str, Any],
    agent_version: str,
    duration: float,
    token_usage: dict[str, int],
) -> tuple[int, float, int, int]:
    """写入 cleaned_data（幂等），返回 (新增条数, 质量分合计, 候选条数, 有分数条数)。

    ``(raw_data_id, dialogue_id)`` 唯一索引 + ``ON CONFLICT DO NOTHING``：
    同一 raw_data 重跑不会重复插入，也不会因唯一约束报错（P1-5）。
    """
    dialogues = result_data.get("dialogues") or []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(dialogues, start=1):
        dialogue_id = str(item.get("dialogue_id") or index)
        parsed_ts = _parse_timestamp(item.get("timestamp"))
        raw_score = item.get("quality_score")
        score = None if raw_score is None else min(100.0, max(0.0, float(raw_score)))
        issues = list(item.get("issues") or [])
        if parsed_ts is None and "missing_timestamp" not in issues:
            issues.append("missing_timestamp")
        rows.append(
            {
                "datasource_id": raw.datasource_id,
                "raw_data_id": raw.id,
                "dialogue_id": _dialogue_uuid(raw.id, dialogue_id),
                "timestamp": parsed_ts,
                "user_message": str(item.get("user_message") or ""),
                "ai_response": str(item.get("ai_response") or ""),
                "metadata": {
                    "agent": item.get("source") or "cleaning_agent",
                    "source": item.get("source"),
                    "source_dialogue_id": dialogue_id,
                    "speaker_pair": item.get("speaker_pair"),
                },
                "quality_score": score,
                "issues": issues,
                "agent_version": agent_version,
                "processing_duration": duration,
                "token_usage": token_usage,
            }
        )
    if not rows:
        return 0, 0.0, 0, 0

    stmt = (
        # 用 Table 而非 ORM 实体做批量 upsert（避免 ORM 批量语义）；
        # mypy 把 __table__ 推断成 FromClause，这里显式忽略参数类型
        pg_insert(CleanedData.__table__)  # type: ignore[arg-type]
        .values(rows)
        .on_conflict_do_nothing(index_elements=["raw_data_id", "dialogue_id"])
        .returning(CleanedData.__table__.c.id, CleanedData.__table__.c.quality_score)
    )
    inserted = (await session.execute(stmt)).all()
    scored = [float(row.quality_score) for row in inserted if row.quality_score is not None]
    return len(inserted), sum(scored), len(rows), len(scored)


async def _execute_clean(
    task_id: uuid.UUID, session: AsyncSession, *, commit: bool
) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        return {"status": "missing", "task_id": str(task_id)}
    if task.status == "cancelled":
        return {"status": "cancelled", "task_id": str(task_id)}
    if task.status == "completed":
        # acks_late 重投递：任务已完成（可能在 ack 前崩溃），直接返回避免重复处理
        return {
            **(task.result or {}),
            "status": "completed",
            "task_id": str(task_id),
            "redelivered": True,
        }

    task.status = "running"
    task.started_at = _now_naive()
    task.progress = 5
    # 重跑（历史任务已是终态）时把状态机复位，避免终态 -> PARSING 的非法跳转
    if _current_state(task) in (CleaningState.COMPLETED, CleaningState.FAILED):
        task.current_step = CleaningState.PENDING.value
    _advance_state(task, CleaningState.PARSING, detail="loading raw data")
    await session.flush()

    cleaned_total = 0
    quality_total = 0.0
    candidate_total = 0
    scored_total = 0
    asr_summary: dict[str, Any] | None = None
    structure_summary: dict[str, Any] | None = None
    raw_records = 0
    failed_raw = 0
    near_duplicates = 0
    datasource: DataSource | None = None

    try:
        raw_items = await _load_raw_items(session, task)
        if not raw_items:
            raise ValueError("no raw data to clean")
        raw_records = len(raw_items)
        config = _config_from_params(task.params or {})

        for index, raw in enumerate(raw_items, start=1):
            # 取消生效：每处理完一个条目检查一次数据库状态（轻量 SELECT）
            if await task_control.is_cancelled(session, task.id):
                await session.refresh(task)
                break

            content = raw.raw_content or {}
            is_media = content.get("format") == "media"

            if is_media:
                asr = content.get("asr") or {}
                if asr.get("status") != "completed":
                    task.current_step = f"parsing asr {index}/{raw_records}"
                    task.progress = max(task.progress or 5, 10)
                    await session.flush()

                async def _report(step: str) -> None:
                    task.current_step = step
                    task.progress = min(40, (task.progress or 10) + 3)
                    await session.flush()

                records, asr_result = await media_pipeline.prepare_media_records(
                    raw,
                    session=session,
                    user_id=task.user_id,
                    on_progress=_report,
                )
                if asr_result:
                    asr_summary = asr_result

                # 单声道整段转写：交给 AI 判断做成 QA / 知识点 / 摘要
                structured = await structure_service.apply(
                    session,
                    raw=raw,
                    records=records,
                    task_id=task.id,
                    user_id=task.user_id,
                    datasource_id=raw.datasource_id,
                )
                if structured:
                    structure_summary = {
                        "content_type": structured.get("content_type"),
                        "structure": structured.get("structure"),
                        "confidence": structured.get("confidence"),
                    }
                if structured and structured.get("structure") == "qa":
                    qa_records = structure_service.qa_to_dialogues(structured)
                    if qa_records:
                        records = qa_records

                _advance_state(task, CleaningState.NORMALIZING, detail=f"{index}/{raw_records}")
                data = {"dialogues": records}
                if not data["dialogues"]:
                    raise ValueError("media transcript has no records")
                agent_version = "asr-1.0"
                duration = 0.0
                token_usage = {"input": 0, "output": 0}
            else:
                # 状态机：NORMALIZING（文本归一化 + LLM 抽取）→ DEDUPLICATING → VALIDATING
                _advance_state(task, CleaningState.NORMALIZING, detail=f"{index}/{raw_records}")
                agent = _build_agent()
                result = await agent.clean(
                    CleaningInput(
                        datasource_id=raw.datasource_id,
                        raw_data=_load_raw_text(raw),
                        data_type=content.get("format") or "txt",
                        config=config,
                    ).model_dump(mode="json"),
                    session=session,
                    task_id=task.id,
                    scope=f"clean:{raw.id}",
                    user_id=task.user_id,
                    datasource_id=raw.datasource_id,
                )

                if not result.success:
                    failed_raw += 1
                    raw.status = "failed"
                    raw.error_message = "; ".join(result.errors)[:1000] or "cleaning failed"
                    # 失败记录同样走完校验阶段，保证下一条能从 VALIDATING 回到 NORMALIZING
                    _advance_state(task, CleaningState.VALIDATING, detail=f"{index}/{raw_records}")
                    await session.flush()
                    continue

                data = result.data or {}
                agent_version = str(result.metadata.get("version", "v1.0.0"))
                duration = result.duration
                token_usage = result.token_usage

            _advance_state(task, CleaningState.DEDUPLICATING, detail=f"{index}/{raw_records}")
            if config.remove_duplicates:
                near_duplicates += _mark_near_duplicates(
                    data.get("dialogues") or [],
                    threshold=config.dedup_threshold,
                )

            _advance_state(task, CleaningState.VALIDATING, detail=f"{index}/{raw_records}")
            created, raw_quality, candidates, scored = await _persist_dialogues(
                session,
                raw=raw,
                result_data=data,
                agent_version=agent_version,
                duration=duration,
                token_usage=token_usage,
            )
            cleaned_total += created
            quality_total += raw_quality
            candidate_total += candidates
            scored_total += scored
            raw.status = "completed"
            raw.processed_at = _now_naive()
            task.progress = min(90, 5 + int(index / raw_records * 85))
            await session.flush()

        datasource = await session.get(DataSource, task.datasource_id)
        if datasource is not None and cleaned_total:
            statistics = dict(datasource.statistics or {})
            statistics.update(
                {
                    "total_records": int(statistics.get("total_records", 0)) + raw_records,
                    "cleaned_records": int(statistics.get("cleaned_records", 0)) + cleaned_total,
                    "quality_score_avg": (
                        round(quality_total / scored_total, 2) if scored_total else 0.0
                    ),
                    "last_processed_at": _now_naive().isoformat(),
                }
            )
            datasource.statistics = statistics
            datasource.workflow_status = "data_cleaned"

        # 最后一条处理期间可能被取消：收尾前复查数据库状态（避免覆盖 cancelled）
        if task.status != "cancelled" and await task_control.is_cancelled(session, task.id):
            await session.refresh(task)

        task.result = {
            "raw_records": raw_records,
            "failed_raw_records": failed_raw,
            "cleaned_records": cleaned_total,
            "skipped_existing_records": max(0, candidate_total - cleaned_total),
            "near_duplicate_records": near_duplicates,
        }
        if asr_summary:
            task.result["asr"] = asr_summary
        if structure_summary:
            task.result["structure"] = structure_summary

        # 用户取消：保留已清洗结果，状态保持 cancelled，不覆盖为 completed/failed
        if task.status == "cancelled":
            await session.flush()
            if commit:
                await session.commit()
            logger.info("clean task cancelled task={} cleaned={}", task.id, cleaned_total)
            return {
                "status": "cancelled",
                "task_id": str(task.id),
                "cleaned_records": cleaned_total,
            }

        # 有候选记录即视为完成：重跑时全部命中唯一索引（0 条新增）也应成功返回
        has_records = bool(cleaned_total or candidate_total)
        task.status = "completed" if has_records else "failed"
        task.progress = 100
        _advance_state(
            task,
            CleaningState.COMPLETED if has_records else CleaningState.FAILED,
            detail=None if has_records else "no_records_cleaned",
        )
        task.completed_at = _now_naive()
        if task.started_at is not None:
            task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
        if not has_records:
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
        try:
            _advance_state(task, CleaningState.FAILED)
        except ValueError:  # 已处于终态（如 completed）时直接兜底写入
            task.current_step = CleaningState.FAILED.value
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
