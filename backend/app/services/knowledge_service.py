"""知识库服务（B-506）。

- 知识提取任务编排（202 + Celery ``tasks.extract_knowledge``）；
- 提取执行：调用 ``KnowledgeExtractionAgent`` → 先删 ``is_seed`` → 插 ``extracted`` →
  盲区写 ``analysis_results``（``analysis_type="knowledge"``，不新建 gaps 表，D-02）；
- FAQ 手动 CRUD（删除为硬删除，API 约定 204）；
- 检索：``pg_trgm`` 相似度 + pgvector 余弦相似度混合排序（向量不可用时降级为纯文本）；
- 盲区：读取最近一次知识提取的 gaps 并按频次分级。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, cast

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.api.deps import assert_owner
from app.api.pagination import PaginationParams, paginate
from app.core.config import settings
from app.core.exceptions import DataSourceNotFoundError, FaqNotFoundError
from app.models import CleanedData, DataSource, KnowledgeBase, Task, User
from app.schemas.agents.extraction import MAX_DIALOGUES_PER_RUN, MAX_EXISTING_QUESTIONS
from app.schemas.knowledge import (
    FAQCreate,
    FAQUpdate,
    GapItem,
    GapsResponse,
    GapsSummary,
    KnowledgeExtractionRequest,
    SearchItem,
    SearchResponse,
)
from app.services import cleaning_service, embedding_service, knowledge_dedup, onboarding_service

EXTRACT_TASK_TYPE = "extract"
MAX_DIALOGUES = 200
MAX_GAP_ITEMS = 200
_SORTABLE: dict[str, InstrumentedAttribute] = {
    "frequency": KnowledgeBase.frequency,
    "created_at": KnowledgeBase.created_at,
}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_agent():  # noqa: ANN202 - 允许测试 monkeypatch
    from app.agents.extraction_agent import KnowledgeExtractionAgent

    return KnowledgeExtractionAgent()


def enqueue_extract(task: Task) -> str:
    from app.tasks.knowledge import extract_knowledge_task

    return str(extract_knowledge_task.delay(str(task.id)))


async def _datasource_or_404(
    session: AsyncSession, datasource_id: uuid.UUID, user: User
) -> DataSource:
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    assert_owner(datasource.user_id, user)
    return datasource


async def _faq_or_404(
    session: AsyncSession, *, datasource_id: uuid.UUID, faq_id: uuid.UUID
) -> KnowledgeBase:
    faq = await session.get(KnowledgeBase, faq_id)
    if faq is None or faq.datasource_id != datasource_id:
        raise FaqNotFoundError(details={"faq_id": str(faq_id)})
    return faq


async def _try_embed(text: str) -> list[float] | None:
    try:
        vectors = await embedding_service.encode_texts([text])
        return vectors[0] if vectors else None
    except Exception as exc:  # noqa: BLE001 - 嵌入失败不阻塞 FAQ 写入
        logger.warning("faq embedding failed: {}", exc)
        return None


# --------------------------------------------------------------------------- 提取任务


async def create_extraction_task(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    request: KnowledgeExtractionRequest,
) -> Task:
    await cleaning_service.ensure_no_running_task(
        session, datasource_id=datasource_id, task_type=EXTRACT_TASK_TYPE
    )
    task = Task(
        task_type=EXTRACT_TASK_TYPE,
        task_name="知识提取",
        datasource_id=datasource_id,
        user_id=user.id,
        params=request.model_dump(),
        status="pending",
        progress=0,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def _load_dialogues(session: AsyncSession, datasource_id: uuid.UUID) -> list[dict[str, Any]]:
    stmt = (
        select(CleanedData)
        .where(CleanedData.datasource_id == datasource_id)
        .order_by(CleanedData.created_at.desc())
        .limit(MAX_DIALOGUES)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [
        {
            "dialogue_id": str(row.dialogue_id),
            "user_message": row.user_message,
            "ai_response": row.ai_response,
        }
        for row in rows
    ]


async def _existing_questions(session: AsyncSession, datasource_id: uuid.UUID) -> list[str]:
    rows = (
        (
            await session.execute(
                select(KnowledgeBase.question).where(
                    KnowledgeBase.datasource_id == datasource_id,
                    KnowledgeBase.is_seed.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    return [str(item) for item in rows]


async def _replace_seed_knowledge(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    """先删 ``is_seed`` 再插入 ``extracted``（B-504 口径）。"""
    result = await session.execute(
        delete(KnowledgeBase).where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.is_seed.is_(True),
        )
    )
    return int(result.rowcount or 0)


def _parse_source_ids(values: list[Any]) -> list[uuid.UUID] | None:
    parsed: list[uuid.UUID] = []
    for value in values:
        try:
            parsed.append(uuid.UUID(str(value)))
        except (ValueError, AttributeError, TypeError):
            continue
    return parsed or None


async def _insert_extracted_faqs(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    faqs: list[dict[str, Any]],
) -> int:
    count = 0
    for item in faqs:
        confidence = float(item.get("confidence", 0.8))
        session.add(
            KnowledgeBase(
                datasource_id=datasource_id,
                question=str(item["question"]),
                answer=str(item["answer"]),
                category=item.get("category") or "其他",
                variations=list(item.get("variations") or []),
                frequency=1,
                quality_score=round(confidence * 100, 1),
                confidence=confidence,
                source_dialogue_ids=_parse_source_ids(item.get("source_dialogue_ids") or []),
                source="extracted",
                is_seed=False,
                status="active",
                embedding=item.get("embedding"),
            )
        )
        count += 1
    return count


async def _save_gaps(
    session: AsyncSession,
    *,
    task: Task,
    gaps: list[dict[str, Any]],
    stats: dict[str, Any],
    faq_count: int,
) -> None:
    """盲区随提取任务持久化在 ``tasks.result``（D-02：不新建 gaps 表）。"""
    task.result = {
        **(task.result or {}),
        "gaps": gaps[:MAX_GAP_ITEMS],
        "gaps_count": len(gaps),
        "statistics": stats,
        "faq_count": faq_count,
    }
    await session.flush()


def _extraction_metrics(
    *,
    dialogue_loaded: int,
    dialogue_unique: int,
    rule_removed: int,
    existing_total: int,
    existing_sent: int,
    select_mode: str,
    fallback_reason: str | None,
    result: Any,
    shadow_removed: int,
    shadow_chars: int,
    shadow_tokens: int,
    source_ids_expanded: int,
) -> dict[str, Any]:
    """T9 Phase 0/1：提取任务的成本与裁剪指标（写入 ``task.result.statistics``）。"""
    usage = result.token_usage or {}
    input_tokens = int(usage.get("input", 0))
    output_tokens = int(usage.get("output", 0))
    top_k = settings.EXTRACTION_QUESTION_TOPK
    return {
        "dialogue_loaded": dialogue_loaded,
        "dialogue_sent": min(dialogue_unique, MAX_DIALOGUES_PER_RUN),
        "dialogue_unique": dialogue_unique,
        "rule_dedup_removed": rule_removed,
        "existing_questions_total": existing_total,
        "existing_questions_sent": min(existing_sent, MAX_EXISTING_QUESTIONS),
        "dedup_mode": "rule" if settings.EXTRACTION_RULE_DEDUP_ENABLED else "off",
        "question_select_mode": select_mode,
        "fallback_reason": fallback_reason,
        "source_ids_expanded": source_ids_expanded,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost": str(result.cost),
        "llm_duration": round(float(result.duration or 0.0), 3),
        "shadow_rule_dedup_removed": shadow_removed,
        "shadow_question_topk_removed": (
            max(0, min(existing_total, MAX_EXISTING_QUESTIONS) - top_k) if top_k > 0 else 0
        ),
        "shadow_prompt_chars_saved_est": shadow_chars,
        "shadow_tokens_saved_est": shadow_tokens,
    }


async def _execute_extraction(
    task_id: uuid.UUID, session: AsyncSession, *, commit: bool
) -> dict[str, Any]:
    task = await session.get(Task, task_id)
    if task is None:
        return {"status": "missing", "task_id": str(task_id)}
    if task.status == "cancelled":
        return {"status": "cancelled", "task_id": str(task_id)}

    datasource_id = task.datasource_id
    if datasource_id is None:
        raise ValueError("extraction task has no datasource")

    task.status = "running"
    task.started_at = _now_naive()
    task.progress = 10
    task.current_step = "loading_cleaned_data"
    await session.flush()

    try:
        dialogues = await _load_dialogues(session, datasource_id)
        if not dialogues:
            raise ValueError("no cleaned data to extract knowledge from")
        existing_all = await _existing_questions(session, datasource_id)

        # T9 Phase 0/1：规则去重（影子值始终计算，便于与开启前基线对比）
        deduped_dialogues, shadow_removed, duplicate_map = knowledge_dedup.dedupe_dialogues(
            dialogues
        )
        if settings.EXTRACTION_RULE_DEDUP_ENABLED:
            unique_dialogues = deduped_dialogues
            rule_removed = shadow_removed
        else:
            unique_dialogues = list(dialogues)
            rule_removed = 0
            duplicate_map = {}

        # T9 Phase 1：既有问题按当前对话语义取 top-k；任何失败自动回退旧行为
        (
            selected_questions,
            select_mode,
            fallback_reason,
        ) = await knowledge_dedup.select_relevant_questions(
            session,
            datasource_id=datasource_id,
            dialogues=unique_dialogues,
            legacy_questions=existing_all,
            top_k=settings.EXTRACTION_QUESTION_TOPK,
            query_chars=settings.EXTRACTION_QUESTION_QUERY_CHARS,
        )

        params = task.params or {}
        agent = _build_agent()
        result = await agent.extract(
            {
                "datasource_id": str(datasource_id),
                "dialogues": unique_dialogues,
                "existing_questions": selected_questions,
                "config": {
                    "max_faqs": int(params.get("max_faq_count", 100)),
                    "min_confidence": 0.0,
                    "include_gaps": True,
                },
            },
            session=session,
            task_id=task.id,
            user_id=task.user_id,
            datasource_id=datasource_id,
        )
        if not result.success or not result.data:
            raise RuntimeError("knowledge extraction failed: " + "; ".join(result.errors))

        data = result.data
        faqs = list(data.get("faqs") or [])
        source_ids_expanded = knowledge_dedup.expand_source_ids(faqs, duplicate_map)
        removed = await _replace_seed_knowledge(session, datasource_id)
        inserted = await _insert_extracted_faqs(
            session,
            datasource_id=datasource_id,
            faqs=faqs,
        )
        task.status = "completed"
        task.progress = 100
        task.current_step = "completed"
        task.completed_at = _now_naive()
        if task.started_at is not None:
            task.duration = round((task.completed_at - task.started_at).total_seconds(), 3)
        shadow_chars, shadow_tokens = knowledge_dedup.estimate_prompt_savings(
            deduped_dialogues=deduped_dialogues,
            removed_dialogues=shadow_removed,
            legacy_questions=existing_all,
            sent_questions=selected_questions,
        )
        statistics = {
            **(data.get("stats") or {}),
            **_extraction_metrics(
                dialogue_loaded=len(dialogues),
                dialogue_unique=len(unique_dialogues),
                rule_removed=rule_removed,
                existing_total=len(existing_all),
                existing_sent=len(selected_questions),
                select_mode=select_mode,
                fallback_reason=fallback_reason,
                result=result,
                shadow_removed=shadow_removed,
                shadow_chars=shadow_chars,
                shadow_tokens=shadow_tokens,
                source_ids_expanded=source_ids_expanded,
            ),
        }
        await _save_gaps(
            session,
            task=task,
            gaps=data.get("gaps") or [],
            stats=statistics,
            faq_count=inserted,
        )
        task.result = {
            **(task.result or {}),
            "faqs_inserted": inserted,
            "seed_removed": removed,
        }
        try:
            await onboarding_service.maybe_mark_knowledge_built(
                session, datasource_id=datasource_id
            )
        except ValueError as exc:  # 状态只进不退，已 ready 时忽略
            logger.info("workflow status unchanged: {}", exc)
        await session.flush()
        if commit:
            await session.commit()
        return {
            "status": "completed",
            "task_id": str(task.id),
            "faqs_inserted": inserted,
        }
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).error("extraction task failed task={}", task.id)
        task.status = "failed"
        task.error_message = str(exc)[:1000]
        task.current_step = "failed"
        task.completed_at = _now_naive()
        await session.flush()
        if commit:
            await session.commit()
        return {"status": "failed", "task_id": str(task.id), "error": str(exc)}


async def run_extraction_task(
    task_id: str, *, session: AsyncSession | None = None
) -> dict[str, Any]:
    if session is not None:
        return await _execute_extraction(uuid.UUID(task_id), session, commit=False)

    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        result = await _execute_extraction(uuid.UUID(task_id), db, commit=True)
    from app.core.database import dispose_engine

    await dispose_engine()
    return result


# --------------------------------------------------------------------------- FAQ CRUD


async def list_faqs(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    params: PaginationParams,
    category: str | None = None,
    min_frequency: int | None = None,
) -> tuple[list[KnowledgeBase], Any]:
    await _datasource_or_404(session, datasource_id, user)
    stmt = select(KnowledgeBase).where(KnowledgeBase.datasource_id == datasource_id)
    if category:
        stmt = stmt.where(KnowledgeBase.category == category)
    if min_frequency is not None:
        stmt = stmt.where(KnowledgeBase.frequency >= min_frequency)
    return await paginate(session, stmt, params, sortable=_SORTABLE)


async def create_faq(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    payload: FAQCreate,
) -> KnowledgeBase:
    await _datasource_or_404(session, datasource_id, user)
    faq = KnowledgeBase(
        datasource_id=datasource_id,
        question=payload.question,
        answer=payload.answer,
        category=payload.category or "其他",
        tags=payload.tags,
        variations=payload.variations,
        frequency=1,
        quality_score=None,
        confidence=None,
        source="manual",
        is_seed=False,
        status="active",
        embedding=await _try_embed(payload.question),
    )
    session.add(faq)
    await session.flush()
    await session.refresh(faq)
    return faq


async def update_faq(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    faq_id: uuid.UUID,
    payload: FAQUpdate,
) -> KnowledgeBase:
    await _datasource_or_404(session, datasource_id, user)
    faq = await _faq_or_404(session, datasource_id=datasource_id, faq_id=faq_id)

    changes = payload.model_dump(exclude_unset=True)
    question_changed = "question" in changes and changes["question"] != faq.question
    for field, value in changes.items():
        setattr(faq, field, value)
    if question_changed:
        faq.embedding = await _try_embed(str(faq.question))
    await session.flush()
    await session.refresh(faq)
    return faq


async def delete_faq(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    faq_id: uuid.UUID,
) -> None:
    await _datasource_or_404(session, datasource_id, user)
    faq = await _faq_or_404(session, datasource_id=datasource_id, faq_id=faq_id)
    await session.delete(faq)
    await session.flush()


# --------------------------------------------------------------------------- 检索 / 盲区


async def search_faqs(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    query: str,
    limit: int = 10,
    threshold: float = 0.3,
) -> SearchResponse:
    await _datasource_or_404(session, datasource_id, user)

    try:
        vectors = await embedding_service.encode_texts([query])
        query_vector = vectors[0] if vectors else None
    except Exception as exc:  # noqa: BLE001 - 向量不可用时降级为纯文本
        logger.warning("knowledge search falls back to trigram: {}", exc)
        query_vector = None

    trigram = func.similarity(KnowledgeBase.question, query)
    if query_vector is not None:
        vector_similarity = 1 - KnowledgeBase.embedding.cosine_distance(query_vector)
        score = trigram * 0.4 + func.coalesce(vector_similarity, 0.0) * 0.6
    else:
        score = trigram
    stmt = (
        select(KnowledgeBase, score.label("similarity"))
        .where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.status == "active",
        )
        .order_by(score.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()

    results: list[SearchItem] = []
    for faq, similarity in rows:
        value = float(similarity or 0)
        if value < threshold:
            continue
        results.append(
            SearchItem(
                id=faq.id,
                question=faq.question,
                answer=faq.answer,
                similarity=round(value, 3),
                category=faq.category,
            )
        )
    return SearchResponse(query=query, results=results, total=len(results))


PriorityLevel = Literal["high", "medium", "low"]


def _priority_for(frequency: int) -> PriorityLevel:
    if frequency >= 10:
        return "high"
    if frequency >= 3:
        return "medium"
    return "low"


async def list_gaps(session: AsyncSession, *, user: User, datasource_id: uuid.UUID) -> GapsResponse:
    await _datasource_or_404(session, datasource_id, user)

    latest_task = await session.scalar(
        select(Task)
        .where(
            Task.datasource_id == datasource_id,
            Task.task_type == EXTRACT_TASK_TYPE,
            Task.status == "completed",
        )
        .order_by(Task.completed_at.desc())
        .limit(1)
    )
    raw_gaps = ((latest_task.result or {}).get("gaps") if latest_task else []) or []
    gaps: list[GapItem] = []
    for item in raw_gaps[:MAX_GAP_ITEMS]:
        frequency = int(item.get("frequency", 1) or 1)
        priority: PriorityLevel = _priority_for(frequency)
        raw_priority = item.get("priority")
        if raw_priority in ("high", "medium", "low"):
            priority = cast(PriorityLevel, raw_priority)
        gaps.append(
            GapItem(
                question=str(item.get("question", "")),
                frequency=frequency,
                category=str(item.get("category") or "其他"),
                priority=priority,
                suggested_answer=item.get("suggested_answer"),
            )
        )
    summary = GapsSummary(
        total_gaps=len(gaps),
        high_priority=sum(1 for gap in gaps if gap.priority == "high"),
        medium_priority=sum(1 for gap in gaps if gap.priority == "medium"),
        low_priority=sum(1 for gap in gaps if gap.priority == "low"),
    )
    return GapsResponse(gaps=gaps, summary=summary)


__all__ = [
    "EXTRACT_TASK_TYPE",
    "create_extraction_task",
    "create_faq",
    "delete_faq",
    "enqueue_extract",
    "list_faqs",
    "list_gaps",
    "run_extraction_task",
    "search_faqs",
    "update_faq",
]
