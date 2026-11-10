"""转写文本结构化与内容路由（应用层）。

职责：
- 对**单声道整段转写**跑一次结构化 Agent，判断内容类型与承载形态；
- 结果写回 ``raw_data.raw_content.structured``（幂等：已结构化则复用）；
- 按形态分流：
  - ``qa``        → 由调用方替换 records，落 ``cleaned_data``；
  - ``knowledge`` → 写 ``knowledge_base``（``status='needs_review'`` 待审核）；
  - ``summary``   → 写 ``analysis_results``（``analysis_type='other'``）。

边界：不感知清洗状态机；失败一律降级为 ``None``（保留整段文本，不阻断清洗）。
"""
from __future__ import annotations

import uuid
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AnalysisResult, KnowledgeBase, RawData
from app.ports.credential import CredentialPort
from app.repositories import analysis_results as analysis_repo
from app.repositories import knowledge_base as knowledge_repo

__all__ = [
    "apply",
    "qa_to_dialogues",
]

MAX_QA_ITEMS = 200
MAX_KNOWLEDGE_ITEMS = 100
SCHEMA_VERSION = 1


def _build_agent(credentials=None):  # noqa: ANN001, ANN202 - 允许测试 monkeypatch
    from app.agents.structure_agent import TranscriptStructureAgent

    return TranscriptStructureAgent(credentials=credentials)


def _is_single_blob(records: list[dict[str, Any]]) -> bool:
    """单声道/双声道同源：只有一条记录且没有说话人配对。"""
    if len(records) != 1:
        return False
    item = records[0] or {}
    return item.get("speaker_pair") == "mono"


def qa_to_dialogues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """把结构化的 QA 结果映射成 ``cleaned_data`` 可写入的记录。"""
    items = payload.get("qa") or []
    dialogues: list[dict[str, Any]] = []
    for index, item in enumerate(items[:MAX_QA_ITEMS], start=1):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question and not answer:
            continue

        raw_score = item.get("quality_score")
        score: float | None
        if raw_score is None:
            score = None
        else:
            try:
                score = min(100.0, max(0.0, float(raw_score)))
            except (TypeError, ValueError):
                score = None

        issues = ["asr_transcript", "speaker_inferred"]
        for extra in item.get("issues") or []:
            text = str(extra).strip()
            if text and text not in issues:
                issues.append(text)

        dialogues.append(
            {
                "dialogue_id": f"qa-{index}",
                "timestamp": None,
                "user_message": question,
                "ai_response": answer,
                "quality_score": score,
                "issues": issues,
                "source": "asr_structured",
                "speaker_pair": "inferred",
            }
        )
    return dialogues


async def _run_agent(
    *,
    session: AsyncSession,
    task_id: uuid.UUID,
    user_id: uuid.UUID | None,
    datasource_id: uuid.UUID,
    text: str,
    duration: float | None,
    channel_mode: str | None,
    credentials: CredentialPort | None = None,
) -> dict[str, Any] | None:
    agent = _build_agent(credentials)
    result = await agent.structure(
        {"text": text, "duration": duration, "channel_mode": channel_mode},
        session=session,
        task_id=task_id,
        scope=f"structure:{task_id}",
        user_id=user_id,
        datasource_id=datasource_id,
    )
    if not result.success or not result.data:
        logger.warning(
            "structure agent failed datasource={} errors={}",
            datasource_id,
            getattr(result, "errors", None),
        )
        return None

    payload = dict(result.data)
    payload["schema_version"] = SCHEMA_VERSION
    payload["agent"] = {
        "name": "structure_agent",
        "version": str(result.metadata.get("version", "v1.0.0")),
        "model": str(result.metadata.get("model", "")) or None,
    }
    return payload


async def _persist_knowledge(
    session: AsyncSession, *, datasource_id: uuid.UUID, payload: dict[str, Any]
) -> int:
    """知识点落库（待审核）。``knowledge_base.source`` 只允许 seed/manual/extracted。"""
    created = 0
    for item in (payload.get("knowledge") or [])[:MAX_KNOWLEDGE_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            continue
        tags = [str(tag).strip()[:50] for tag in (item.get("tags") or []) if str(tag).strip()]
        await knowledge_repo.add(
            session,
            KnowledgeBase(
                datasource_id=datasource_id,
                question=title[:2000],
                answer=content,
                category=str(payload.get("content_type") or "other")[:100],
                tags=tags[:10] or None,
                source="extracted",
                is_seed=False,
                confidence=payload.get("confidence"),
                status="needs_review",
            ),
        )
        created += 1
    if created:
        await session.flush()
    return created


async def _persist_summary(
    session: AsyncSession, *, datasource_id: uuid.UUID, payload: dict[str, Any]
) -> bool:
    """摘要落库（``analysis_type='other'``，不污染洞察视图）。"""
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        return False
    await analysis_repo.add(
        session,
        AnalysisResult(
            datasource_id=datasource_id,
            data_id=None,
            analysis_type="other",
            result={
                "kind": "transcript_summary",
                "content_type": payload.get("content_type"),
                "summary": summary,
                "confidence": payload.get("confidence"),
                "schema_version": SCHEMA_VERSION,
            },
            agent_name="structure_agent",
            agent_version=str((payload.get("agent") or {}).get("version") or "v1.0.0"),
            ai_model=(payload.get("agent") or {}).get("model"),
            confidence=payload.get("confidence"),
        ),
    )
    await session.flush()
    return True


async def apply(
    session: AsyncSession,
    *,
    raw: RawData,
    records: list[dict[str, Any]],
    task_id: uuid.UUID,
    user_id: uuid.UUID | None,
    datasource_id: uuid.UUID,
    credentials: CredentialPort | None = None,
) -> dict[str, Any] | None:
    """对单声道整段转写做结构化，并按形态分流；不可用时返回 ``None``。

    ``credentials`` 由调用方（services 层）注入，application 不依赖 services。
    """
    if not settings.MEDIA_STRUCTURE_ENABLED:
        return None

    content = raw.raw_content or {}
    existing = content.get("structured")
    if isinstance(existing, dict):
        return existing

    if not _is_single_blob(records):
        return None

    text = str(content.get("text") or "").strip()
    if len(text) < settings.MEDIA_STRUCTURE_MIN_CHARS:
        return None

    media = content.get("media") or {}
    payload = await _run_agent(
        session=session,
        task_id=task_id,
        user_id=user_id,
        datasource_id=datasource_id,
        text=text,
        duration=media.get("duration"),
        channel_mode=media.get("channel_mode"),
        credentials=credentials,
    )
    if payload is None:
        return None

    raw.raw_content = {**content, "structured": payload}
    structure = payload.get("structure")
    if structure == "knowledge":
        await _persist_knowledge(session, datasource_id=datasource_id, payload=payload)
    elif structure == "summary":
        await _persist_summary(session, datasource_id=datasource_id, payload=payload)
    await session.flush()

    logger.info(
        "media structured datasource={} type={} structure={} confidence={}",
        datasource_id,
        payload.get("content_type"),
        structure,
        payload.get("confidence"),
    )
    return payload
