"""切分任务（structure）：转写与切分解耦后的第二步。

- 一个任务只处理一个音视频文件（raw）；
- 前置条件：``raw_content.asr.status == completed``（先转写，再切分）；
- 结果：**整体替换**该 raw 派生的 ``cleaned_data``（删旧插新），
  修复「重跑按位置合并、新旧混排」的问题；
- 失败：结构化原因已写入 ``raw_content.structure_error``，任务置 failed，可单独重试。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import structure_service
from app.core.config import settings
from app.core.errors import FrameworkErrorCode
from app.core.exceptions import AIInsightHubException, TaskAlreadyRunningError
from app.models import AnalysisResult, KnowledgeBase, RawData, Task
from app.repositories import cleaned_data as cleaned_repo
from app.services import cleaning_service
from app.services.credential_service import credential_service

STRUCTURE_TASK_TYPE = "structure"

# 无需切分时的兜底：保留整段文本为一条记录（不调用 LLM，不判失败）
FALLBACK_REASONS = {
    "structure_disabled": "内容结构化已关闭，已保留整段文本",
    "text_too_short": "音频过短（转写文本低于结构化阈值），已保留整段文本",
}

__all__ = [
    "STRUCTURE_TASK_TYPE",
    "create_structure_task",
    "run_structure_task",
    "structure_state",
]


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _conflict(message: str) -> AIInsightHubException:
    return AIInsightHubException(message, code=FrameworkErrorCode.HTTP_ERROR, status_code=409)


def structure_state(raw: RawData) -> dict[str, Any]:
    """一个文件当前的「转写 / 切分」状态（供 API 列表与任务结果使用）。"""
    content = raw.raw_content or {}
    asr = content.get("asr") or {}
    structured = content.get("structured")
    error = content.get("structure_error") or {}
    skipped = content.get("structure_skipped") or {}
    if isinstance(structured, dict):
        structure_status = "done"
    elif error:
        structure_status = "failed"
    elif skipped:
        structure_status = "skipped"
    else:
        structure_status = "pending"
    qa = (structured or {}).get("qa") if isinstance(structured, dict) else []
    return {
        "asr_status": asr.get("status") or "pending",
        "structure_status": structure_status,
        "structure_kind": (structured or {}).get("structure")
        if isinstance(structured, dict)
        else None,
        "qa_count": len(qa or []),
        "partial": bool((structured or {}).get("partial"))
        if isinstance(structured, dict)
        else False,
        "error": str(error.get("message"))[:500] if error and not structured else None,
        # 无需切分时的说明（短音频 / 结构化关闭），已保留整段文本
        "note": str(skipped.get("reason"))[:200] if skipped and not structured else None,
    }


def _assert_ready(raw: RawData) -> None:
    """切分前置：必须是已转写的单声道音视频，否则给出可读原因。"""
    content = raw.raw_content or {}
    if content.get("format") != "media":
        raise _conflict("只有音视频文件需要切分（文本数据在清洗阶段直接产出对话）")
    asr = content.get("asr") or {}
    if asr.get("status") != "completed":
        raise _conflict(f"该文件尚未完成转写（asr_status={asr.get('status') or 'pending'}），请先等待转写")
    records = content.get("records") or []
    if not structure_service.is_single_mono(records):
        raise _conflict("双声道记录已按左右声道配对为对话，无需再切分")


def _fallback_code(raw: RawData) -> str | None:
    """本来就不需要切分的情况（关闭结构化 / 文本过短）→ 返回兜底原因码。"""
    if not settings.MEDIA_STRUCTURE_ENABLED:
        return "structure_disabled"
    text = str((raw.raw_content or {}).get("text") or "").strip()
    if len(text) < settings.MEDIA_STRUCTURE_MIN_CHARS:
        return "text_too_short"
    return None


async def _apply_fallback(session: AsyncSession, raw: RawData, code: str) -> tuple[int, int]:
    """把整段转写落成一条记录（替换旧结果），返回 ``(新增, 被替换)``。"""
    content = raw.raw_content or {}
    records = [item for item in (content.get("records") or []) if isinstance(item, dict)]
    if not records:
        records = [
            {
                "dialogue_id": "asr-1",
                "timestamp": None,
                "user_message": str(content.get("text") or "").strip(),
                "ai_response": "",
                "quality_score": None,
                "issues": ["asr_transcript", "mono_speaker_unknown"],
                "source": "asr",
                "speaker_pair": "mono",
            }
        ]
    for record in records:
        issues = list(record.get("issues") or [])
        if "structure_unparsed" not in issues:
            issues.append("structure_unparsed")
        record["issues"] = issues

    removed = await cleaned_repo.delete_for_raw(session, raw.id)
    created, _, _, _ = await cleaning_service.persist_dialogues(
        session,
        raw=raw,
        result_data={"dialogues": records},
        agent_version="asr-1.0",
        duration=0.0,
        token_usage={"input": 0, "output": 0},
    )
    updated = {
        **content,
        "structure_skipped": {
            "code": code,
            "reason": FALLBACK_REASONS[code],
            "at": _now_naive().isoformat(),
        },
    }
    updated.pop("structure_error", None)
    raw.raw_content = updated
    return created, removed


async def _artifact_ids(
    session: AsyncSession, raw_id: uuid.UUID
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """切分产物（知识点 / 摘要）按文件归属的旧记录 id，用于「替换」时精确删除。"""
    knowledge_ids = list(
        (await session.execute(select(KnowledgeBase.id).where(KnowledgeBase.raw_data_id == raw_id)))
        .scalars()
        .all()
    )
    summary_ids = list(
        (
            await session.execute(
                select(AnalysisResult.id).where(
                    AnalysisResult.raw_data_id == raw_id,
                    AnalysisResult.analysis_type == "other",
                )
            )
        )
        .scalars()
        .all()
    )
    return knowledge_ids, summary_ids


async def _delete_artifacts(
    session: AsyncSession, knowledge_ids: list[uuid.UUID], summary_ids: list[uuid.UUID]
) -> None:
    """删除上一次切分产出（只删捕获到的旧 id，不会误删本次新写入的行）。"""
    if knowledge_ids:
        await session.execute(delete(KnowledgeBase).where(KnowledgeBase.id.in_(knowledge_ids)))
    if summary_ids:
        await session.execute(delete(AnalysisResult).where(AnalysisResult.id.in_(summary_ids)))


async def _running_structure_task(session: AsyncSession, raw_id: uuid.UUID) -> Task | None:
    return (
        (
            await session.execute(
                select(Task)
                .where(
                    Task.task_type == STRUCTURE_TASK_TYPE,
                    Task.status.in_(("pending", "running")),
                    Task.params["raw_data_id"].astext == str(raw_id),
                )
                .order_by(Task.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def create_structure_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    raw: RawData,
) -> Task:
    """建一个切分任务（不改状态、不入队，由调用方决定何时入队）。"""
    _assert_ready(raw)
    if await _running_structure_task(session, raw.id) is not None:
        raise TaskAlreadyRunningError(
            details={"raw_data_id": str(raw.id), "task_type": STRUCTURE_TASK_TYPE}
        )
    task = Task(
        task_type=STRUCTURE_TASK_TYPE,
        task_name="转写切分",
        datasource_id=raw.datasource_id,
        user_id=user_id,
        params={"raw_data_id": str(raw.id)},
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def _execute(task_id: uuid.UUID, session: AsyncSession, *, commit: bool) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        return {"status": "missing", "task_id": str(task_id)}
    if task.status == "cancelled":
        return {"status": "cancelled", "task_id": str(task_id)}

    raw_id = (task.params or {}).get("raw_data_id")
    if not raw_id:
        task.status = "failed"
        task.error_message = "structure task has no raw_data_id"
        task.current_step = "failed"
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id)}

    raw = await session.get(RawData, uuid.UUID(str(raw_id)))
    if raw is None:
        task.status = "failed"
        task.error_message = "raw data not found"
        task.current_step = "failed"
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id)}

    task.status = "running"
    task.started_at = _now_naive()
    task.progress = 10
    task.current_step = "structuring"
    await session.flush()

    try:
        _assert_ready(raw)

        fallback = _fallback_code(raw)
        if fallback is not None:
            created, removed = await _apply_fallback(session, raw, fallback)
            task.status = "completed"
            task.progress = 100
            task.current_step = "structure_skipped"
            task.result = {
                "structure": {"structure": "raw_text", "skipped_reason": fallback},
                "replaced": removed,
                "created": created,
                "state": structure_state(raw),
            }
            await _refresh_datasource_statistics(session, raw.datasource_id)
            task.completed_at = _now_naive()
            if task.started_at is not None:
                task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
            await session.flush()
            if commit:
                await session.commit()
            logger.info(
                "structure task skipped task={} raw={} reason={} created={}",
                task.id,
                raw.id,
                fallback,
                created,
            )
            return {
                "status": task.status,
                "task_id": str(task.id),
                "raw_data_id": str(raw.id),
                **(task.result or {}),
            }

        content = raw.raw_content or {}
        # 显式重跑：清掉上一次的结构化结果/错误标记，否则 apply() 会直接复用旧结果
        if any(key in content for key in ("structured", "structure_error", "structure_skipped")):
            raw.raw_content = {
                key: value
                for key, value in content.items()
                if key not in ("structured", "structure_error", "structure_skipped")
            }
            content = raw.raw_content
            await session.flush()
        # 先记下上一次切分产出的知识点/摘要，成功后精确删除（替换语义）
        old_knowledge_ids, old_summary_ids = await _artifact_ids(session, raw.id)
        payload = await structure_service.apply(
            session,
            raw=raw,
            records=list(content.get("records") or []),
            task_id=task.id,
            user_id=task.user_id,
            datasource_id=raw.datasource_id,
            credentials=credential_service,
        )

        state = structure_state(raw)
        if payload is None:
            task.status = "failed"
            task.progress = 100
            task.current_step = "structure_failed"
            task.error_message = state.get("error") or "structure failed"
            task.result = {"state": state}
        else:
            # 切分成功：清掉之前可能残留的「无需切分」标记
            if (raw.raw_content or {}).get("structure_skipped"):
                raw.raw_content = {
                    key: value
                    for key, value in (raw.raw_content or {}).items()
                    if key != "structure_skipped"
                }
            # 整体替换：先删该文件派生的旧对话，再按新结果写入（避免新旧混排）
            removed = await cleaned_repo.delete_for_raw(session, raw.id)
            created = 0
            if payload.get("structure") == "qa":
                dialogues = structure_service.qa_to_dialogues(payload)
                if dialogues:
                    created, _, _, _ = await cleaning_service.persist_dialogues(
                        session,
                        raw=raw,
                        result_data={"dialogues": dialogues},
                        agent_version="asr-1.0",
                        duration=0.0,
                        token_usage={"input": 0, "output": 0},
                    )
            # 知识点 / 摘要同样整体替换（只删上一次捕获到的旧记录）
            await _delete_artifacts(session, old_knowledge_ids, old_summary_ids)
            task.status = "completed"
            task.progress = 100
            task.current_step = "completed"
            task.result = {
                "structure": {
                    "structure": payload.get("structure"),
                    "content_type": payload.get("content_type"),
                    "confidence": payload.get("confidence"),
                    "chunks": (payload.get("merge") or {}).get("chunks"),
                    "partial": bool(payload.get("partial")),
                },
                "replaced": removed,
                "created": created,
                "replaced_artifacts": {
                    "knowledge": len(old_knowledge_ids),
                    "summary": len(old_summary_ids),
                },
                "state": state,
            }
            await _refresh_datasource_statistics(session, raw.datasource_id)

        task.completed_at = _now_naive()
        if task.started_at is not None:
            task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
        await session.flush()
        if commit:
            await session.commit()
        logger.info(
            "structure task done task={} raw={} status={} created={}",
            task.id,
            raw.id,
            task.status,
            (task.result or {}).get("created"),
        )
        return {
            "status": task.status,
            "task_id": str(task.id),
            "raw_data_id": str(raw.id),
            **(task.result or {}),
        }
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).error("structure task failed task={}", task.id)
        task.status = "failed"
        task.progress = 100
        task.current_step = "failed"
        task.error_message = str(exc)[:1000]
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id), "error": str(exc)}


async def _refresh_datasource_statistics(session: AsyncSession, datasource_id: uuid.UUID) -> None:
    """切分会整体替换对话行，数据源的 cleaned_records / 均分需要按实际值回写。"""
    from app.models import DataSource, CleanedData

    datasource = await session.get(DataSource, datasource_id)
    if datasource is None:
        return
    row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.avg(CleanedData.quality_score).label("avg_score"),
            ).where(CleanedData.datasource_id == datasource_id)
        )
    ).one()
    statistics = dict(datasource.statistics or {})
    statistics.update(
        {
            "cleaned_records": int(row.total or 0),
            "quality_score_avg": round(float(row.avg_score or 0), 2),
            "last_processed_at": _now_naive().isoformat(),
        }
    )
    datasource.statistics = statistics
    datasource.workflow_status = "data_cleaned"


async def run_structure_task(
    task_id: str, *, session: AsyncSession | None = None
) -> dict[str, Any]:
    """执行切分任务（Celery 入口与测试共用）。"""
    if session is not None:
        return await _execute(uuid.UUID(task_id), session, commit=False)

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        result = await _execute(uuid.UUID(task_id), db, commit=True)
    from app.core.database import dispose_engine

    await dispose_engine()
    return result
