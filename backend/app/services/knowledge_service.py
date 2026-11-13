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
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Literal, cast

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


if TYPE_CHECKING:
    from app.agents.extraction_agent import KnowledgeExtractionAgent

from app.core.ownership import assert_owner
from app.core.pagination import PaginationParams
from app.application import task_control
from app.core.config import settings
from app.core.exceptions import DataSourceNotFoundError, FaqNotFoundError, GapNotFoundError
from app.repositories import cleaned_data as cleaned_repo
from app.repositories import knowledge_base as knowledge_repo
from app.repositories import knowledge_gaps as knowledge_gap_repo
from app.models import CleanedData, DataSource, KnowledgeBase, Task, User
from app.schemas.agents.extraction import MAX_DIALOGUES_PER_RUN, MAX_EXISTING_QUESTIONS
from app.schemas.knowledge import (
    CoverageResponse,
    FAQCreate,
    FAQUpdate,
    GapItem,
    GapsResponse,
    GapsSummary,
    KnowledgeExtractionRequest,
    SearchItem,
    SearchResponse,
)
from app.services.credential_service import credential_service
from app.services import cleaning_service, embedding_service, knowledge_dedup, onboarding_service

EXTRACT_TASK_TYPE = "extract"
MAX_DIALOGUES = 200
MAX_GAP_ITEMS = 200


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_agent() -> KnowledgeExtractionAgent:  # 允许测试 monkeypatch
    from app.agents.extraction_agent import KnowledgeExtractionAgent

    return KnowledgeExtractionAgent(
        embed=embedding_service.encode_texts_sync,
        credentials=credential_service,
    )


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
    faq = await knowledge_repo.get(session, faq_id)
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
    rows = await cleaned_repo.list_for_analysis(
        session, datasource_id, limit=MAX_DIALOGUES, newest_first=True
    )
    return [
        {
            "dialogue_id": str(row.dialogue_id),
            "user_message": row.user_message,
            "ai_response": row.ai_response,
        }
        for row in rows
    ]


async def _existing_questions(session: AsyncSession, datasource_id: uuid.UUID) -> list[str]:
    return await knowledge_repo.existing_questions(session, datasource_id)


async def _replace_seed_knowledge(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    """先删 ``is_seed`` 再插入 ``extracted``（B-504 口径）。"""
    return await knowledge_repo.delete_seed(session, datasource_id)


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
    """盲区写台账（累积） + 仍保留在 ``tasks.result``（兼容旧读法）。

    台账化之后重跑不再覆盖：``hit_count`` 累加、``first_seen/last_seen`` 更新、
    ``open/adopted/ignored`` 状态由人工流转。
    """
    task.result = {
        **(task.result or {}),
        "gaps": gaps[:MAX_GAP_ITEMS],
        "gaps_count": len(gaps),
        "statistics": stats,
        "faq_count": faq_count,
    }
    if task.datasource_id is not None:
        await knowledge_gap_repo.upsert_many(
            session,
            datasource_id=task.datasource_id,
            gaps=gaps[:MAX_GAP_ITEMS],
            task_id=task.id,
        )
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
            scope="extract",
            user_id=task.user_id,
            datasource_id=datasource_id,
        )
        if not result.success or not result.data:
            raise RuntimeError("knowledge extraction failed: " + "; ".join(result.errors))

        # Agent 调用期间可能被取消：保留种子知识、状态保持 cancelled
        if await task_control.is_cancelled(session, task.id):
            await session.refresh(task)
            return {"status": "cancelled", "task_id": str(task.id), "faqs_inserted": 0}

        data = result.data
        faqs = list(data.get("faqs") or [])
        source_ids_expanded = knowledge_dedup.expand_source_ids(faqs, duplicate_map)
        if faqs:
            removed = await _replace_seed_knowledge(session, datasource_id)
            inserted = await _insert_extracted_faqs(
                session,
                datasource_id=datasource_id,
                faqs=faqs,
            )
        else:
            # 合法空结果（如数据无新知识）：保留种子 FAQ，避免知识库被清空（P1-3）
            logger.warning(
                "extraction returned no faqs, keep seed knowledge datasource={}", datasource_id
            )
            removed, inserted = 0, 0
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
    status: str | None = None,
) -> tuple[list[KnowledgeBase], Any]:
    await _datasource_or_404(session, datasource_id, user)
    return await knowledge_repo.list_for_datasource(
        session,
        datasource_id,
        params=params,
        category=category,
        min_frequency=min_frequency,
        status=status,
    )


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

    rows = await knowledge_repo.search(
        session,
        datasource_id,
        query=query,
        query_vector=query_vector,
        limit=limit,
    )

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


async def list_gaps(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    status: str | None = None,
) -> GapsResponse:
    """盲区台账（累积，不再依赖最近一次提取任务的快照）。"""
    await _datasource_or_404(session, datasource_id, user)

    rows = await knowledge_gap_repo.list_for_datasource(
        session, datasource_id, status=status, limit=MAX_GAP_ITEMS
    )
    gaps: list[GapItem] = []
    for row in rows:
        frequency = int(row.hit_count or 1)
        priority: PriorityLevel = _priority_for(frequency)
        if row.priority in ("high", "medium", "low"):
            priority = cast(PriorityLevel, row.priority)
        gaps.append(
            GapItem(
                id=row.id,
                question=row.question,
                frequency=frequency,
                priority=priority,
                status=cast(Any, row.status),
                faq_id=row.faq_id,
                first_seen=row.first_seen,
                last_seen=row.last_seen,
            )
        )
    counts = await knowledge_gap_repo.count_by_status(session, datasource_id)
    summary = GapsSummary(
        total_gaps=sum(counts.values()),
        open_gaps=counts.get("open", 0),
        adopted_gaps=counts.get("adopted", 0),
        ignored_gaps=counts.get("ignored", 0),
        high_priority=sum(1 for gap in gaps if gap.priority == "high"),
        medium_priority=sum(1 for gap in gaps if gap.priority == "medium"),
        low_priority=sum(1 for gap in gaps if gap.priority == "low"),
    )
    return GapsResponse(gaps=gaps, summary=summary)


async def update_gap_status(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    gap_id: uuid.UUID,
    status: str,
    faq_id: uuid.UUID | None = None,
) -> GapItem:
    """盲区状态流转：open（待处理）/ adopted（已采纳为 FAQ）/ ignored（不处理）。"""
    await _datasource_or_404(session, datasource_id, user)
    gap = await knowledge_gap_repo.get(session, gap_id)
    if gap is None or gap.datasource_id != datasource_id:
        raise GapNotFoundError(details={"gap_id": str(gap_id)})
    gap.status = status
    if faq_id is not None:
        gap.faq_id = faq_id
    await session.flush()
    await session.refresh(gap)
    frequency = int(gap.hit_count or 1)
    return GapItem(
        id=gap.id,
        question=gap.question,
        frequency=frequency,
        priority=_priority_for(frequency),
        status=cast(Any, gap.status),
        faq_id=gap.faq_id,
        first_seen=gap.first_seen,
        last_seen=gap.last_seen,
    )


async def coverage(
    session: AsyncSession,
    *,
    user: User,
    datasource_id: uuid.UUID,
    days: int = 7,
    threshold: float = 0.8,
) -> CoverageResponse:
    """知识覆盖率：最近 N 天的对话里，有多少能被现有 FAQ 命中。

    - 有 embedding 的对话走向量（余弦相似度 ≥ 阈值）；
    - 当前 `cleaned_data.embedding` 尚未全量回填，窗口内没有向量时**降级为文本相似度**
      （pg_trgm），并在响应里标注 ``method="trgm"``，避免给出「0%」的假结论。
    """
    await _datasource_or_404(session, datasource_id, user)
    since = _now_naive() - timedelta(days=days)
    window = [
        CleanedData.datasource_id == datasource_id,
        CleanedData.created_at >= since,
    ]

    max_distance = max(0.0, min(1.0, 1.0 - threshold))
    vector_match = (
        select(KnowledgeBase.id)
        .where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.status == "active",
            KnowledgeBase.embedding.isnot(None),
            CleanedData.embedding.isnot(None),
            CleanedData.embedding.cosine_distance(KnowledgeBase.embedding) <= max_distance,
        )
        .exists()
    )
    vector_row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(vector_match).label("covered"),
            ).where(*window, CleanedData.embedding.isnot(None))
        )
    ).one()
    total = int(vector_row.total or 0)
    covered = int(vector_row.covered or 0)
    if total:
        return CoverageResponse(
            datasource_id=datasource_id,
            days=days,
            threshold=threshold,
            total=total,
            covered=covered,
            rate=round(covered / total, 4),
            method="vector",
        )

    # 降级：文本相似度（pg_trgm），无需 embedding，历史数据也能给出参考值
    text_match = (
        select(KnowledgeBase.id)
        .where(
            KnowledgeBase.datasource_id == datasource_id,
            KnowledgeBase.status == "active",
            func.similarity(CleanedData.user_message, KnowledgeBase.question) >= threshold,
        )
        .exists()
    )
    text_row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(text_match).label("covered"),
            ).where(*window)
        )
    ).one()
    total = int(text_row.total or 0)
    covered = int(text_row.covered or 0)
    return CoverageResponse(
        datasource_id=datasource_id,
        days=days,
        threshold=threshold,
        total=total,
        covered=covered,
        rate=round(covered / total, 4) if total else 0.0,
        method="trgm",
    )


__all__ = [
    "EXTRACT_TASK_TYPE",
    "coverage",
    "create_extraction_task",
    "create_faq",
    "delete_faq",
    "list_faqs",
    "list_gaps",
    "run_extraction_task",
    "search_faqs",
    "update_gap_status",
    "update_faq",
]
