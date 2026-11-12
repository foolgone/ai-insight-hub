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

import re
import uuid
from collections import Counter
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
    "is_single_mono",
    "merge_payloads",
    "qa_to_dialogues",
    "split_transcript",
]

MAX_QA_ITEMS = 200
MAX_KNOWLEDGE_ITEMS = 100
SCHEMA_VERSION = 1
# 分块参数：39 分钟面试 ≈ 9.3k 字，一次调用必然打满输出 token（实测 6.5k），
# 切成 ~2.5k 字/块后每块输出只有几百 token，既不会被截断，失败也只影响一块。
CHUNK_MAX_CHARS = 2500
MAX_CHUNKS = 12
# 合并后的摘要上限（多块拼接不应无限长）
MAX_SUMMARY_CHARS = 1200
_SENTENCE_ENDS = frozenset("。！？!?；;\n")

_WHITESPACE = re.compile(r"\s+")


def _sentences(text: str) -> list[str]:
    """按句末标点切句（保留标点）；没有标点时整段作为一句。"""
    sentences: list[str] = []
    buffer: list[str] = []
    for char in text:
        buffer.append(char)
        if char in _SENTENCE_ENDS:
            sentence = "".join(buffer).strip()
            if sentence:
                sentences.append(sentence)
            buffer = []
    tail = "".join(buffer).strip()
    if tail:
        sentences.append(tail)
    return sentences


def split_transcript(
    text: str,
    *,
    max_chars: int = CHUNK_MAX_CHARS,
    max_chunks: int = MAX_CHUNKS,
) -> list[str]:
    """把长转写按句子边界切成若干块（每块尽量 ≤ ``max_chars``）。

    设计取舍：
    - **按句切、不按字数硬切**，避免把「提问」和「回答」切到两个块里；
    - 单句超长时才对半硬切；
    - 块数超过 ``max_chunks`` 时把余下内容并入最后一块（宁可超长，不丢内容）。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("".join(current).strip())
            current = []
            current_len = 0

    for sentence in _sentences(cleaned):
        if len(sentence) > max_chars:
            # 单句超长（ASR 没标点）：先冲刷当前块，再对半硬切
            flush()
            for start in range(0, len(sentence), max_chars):
                chunks.append(sentence[start : start + max_chars])
            continue
        if current_len + len(sentence) > max_chars:
            flush()
        current.append(sentence)
        current_len += len(sentence)
    flush()

    if len(chunks) > max_chunks:
        head = chunks[: max_chunks - 1]
        tail = "".join(chunks[max_chunks - 1 :])
        logger.warning(
            "transcript too long, merged tail chunks total_chars={} max_chunks={}",
            len(cleaned),
            max_chunks,
        )
        return [*head, tail]
    return [chunk for chunk in chunks if chunk]


def _normalize(text: str) -> str:
    return _WHITESPACE.sub("", str(text or "")).lower()


def _merge_qa(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并多块 QA：按「问题+答案」归一化去重，重复时保留更高的质量分。"""
    merged: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        for item in payload.get("qa") or []:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if not question and not answer:
                continue
            key = _normalize(question) + "||" + _normalize(answer)
            existing = merged.get(key)
            if existing is None:
                merged[key] = {
                    "question": question,
                    "answer": answer,
                    "quality_score": item.get("quality_score"),
                    "issues": list(item.get("issues") or []),
                }
                continue
            current = existing.get("quality_score")
            candidate = item.get("quality_score")
            if isinstance(candidate, (int, float)) and (
                not isinstance(current, (int, float)) or candidate > current
            ):
                existing["quality_score"] = candidate
    return list(merged.values())[:MAX_QA_ITEMS]


def _merge_knowledge(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        for item in payload.get("knowledge") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            if not title or not content:
                continue
            key = _normalize(title)
            merged.setdefault(
                key,
                {
                    "title": title,
                    "content": content,
                    "tags": [str(tag)[:50] for tag in (item.get("tags") or []) if str(tag)][:10],
                },
            )
    return list(merged.values())[:MAX_KNOWLEDGE_ITEMS]


def merge_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """把逐块的结构化结果合并成一个整体结果（纯函数，便于单测）。

    - ``content_type``：多数票（``other`` 不参与投票，全为 other 时取 other）；
    - ``structure``：只要有任意一块切出了 QA 就按 QA 合并（QA 信息量最大），
      否则看 knowledge，最后才是 summary；
    - ``confidence``：取各块均值（块越多整体越稳）。
    """
    if not payloads:
        raise ValueError("merge_payloads requires at least one payload")

    types = [str(payload.get("content_type") or "other") for payload in payloads]
    voted = [item for item in types if item != "other"]
    content_type = Counter(voted).most_common(1)[0][0] if voted else "other"

    qa_items = _merge_qa(payloads)
    knowledge_items = _merge_knowledge(payloads)
    summaries = [
        str(payload.get("summary") or "").strip()
        for payload in payloads
        if str(payload.get("summary") or "").strip()
    ]

    if qa_items:
        structure = "qa"
    elif knowledge_items:
        structure = "knowledge"
    else:
        structure = "summary"

    summary: str | None = None
    if summaries:
        joined = "\n\n".join(summaries)
        summary = joined[:MAX_SUMMARY_CHARS]

    confidences: list[float] = []
    for payload in payloads:
        raw_confidence = payload.get("confidence")
        if isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool):
            confidences.append(float(raw_confidence))
    confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    rationale = "；".join(
        item
        for item in (str(payload.get("rationale") or "").strip() for payload in payloads)
        if item
    )[:500]

    return {
        "content_type": content_type,
        "structure": structure,
        "confidence": confidence,
        "qa": qa_items,
        "knowledge": knowledge_items,
        "summary": summary,
        "rationale": rationale,
        "merge": {
            "chunks": len(payloads),
            "structure_votes": dict(Counter(str(p.get("structure") or "") for p in payloads)),
        },
    }


def _build_agent(credentials=None):  # noqa: ANN001, ANN202 - 允许测试 monkeypatch
    from app.agents.structure_agent import TranscriptStructureAgent

    return TranscriptStructureAgent(credentials=credentials)


def is_single_mono(records: list[dict[str, Any]]) -> bool:
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
    chunk_index: int = 0,
) -> tuple[dict[str, Any] | None, str | None]:
    """跑一块结构化，返回 ``(payload, error)``；不抛异常，便于逐块失败隔离。"""
    agent = _build_agent(credentials)
    result = await agent.structure(
        {"text": text, "duration": duration, "channel_mode": channel_mode},
        session=session,
        task_id=task_id,
        # 分块后每块的幂等键要区分，否则 llm_calls 里多块会互相覆盖
        scope=f"structure:{task_id}:{chunk_index}",
        user_id=user_id,
        datasource_id=datasource_id,
    )
    if not result.success or not result.data:
        errors = getattr(result, "errors", None) or ["structure failed"]
        logger.warning(
            "structure agent failed datasource={} chunk={} errors={}",
            datasource_id,
            chunk_index,
            errors,
        )
        return None, "; ".join(str(item) for item in errors)[:300]

    payload = dict(result.data)
    payload["agent"] = {
        "name": "structure_agent",
        "version": str(result.metadata.get("version", "v1.0.0")),
        "model": str(result.metadata.get("model", "")) or None,
    }
    return payload, None


async def _persist_knowledge(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    raw_data_id: uuid.UUID,
    payload: dict[str, Any],
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
                raw_data_id=raw_data_id,
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
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    task_id: uuid.UUID,
    raw_data_id: uuid.UUID,
    payload: dict[str, Any],
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
            task_id=task_id,
            raw_data_id=raw_data_id,
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

    if not is_single_mono(records):
        return None

    text = str(content.get("text") or "").strip()
    if len(text) < settings.MEDIA_STRUCTURE_MIN_CHARS:
        return None

    media = content.get("media") or {}
    chunks = split_transcript(text)
    if not chunks:
        return None

    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, chunk in enumerate(chunks):
        payload, error = await _run_agent(
            session=session,
            task_id=task_id,
            user_id=user_id,
            datasource_id=datasource_id,
            text=chunk,
            duration=media.get("duration"),
            channel_mode=media.get("channel_mode"),
            credentials=credentials,
            chunk_index=index,
        )
        if payload is None:
            errors.append(f"chunk {index + 1}/{len(chunks)}: {error or 'failed'}")
            continue
        payloads.append(payload)

    if not payloads:
        # 全部失败：把原因写回 raw，供调用方展示与重跑（不再静默降级）
        message = "; ".join(errors)[:500] or "structure failed"
        raw.raw_content = {
            **content,
            "structure_error": {"message": message, "chunks": len(chunks)},
        }
        await session.flush()
        logger.warning(
            "media structure failed datasource={} chunks={} errors={}",
            datasource_id,
            len(chunks),
            message,
        )
        return None

    payload = merge_payloads(payloads)
    payload["schema_version"] = SCHEMA_VERSION
    payload["agent"] = payloads[0].get("agent")
    if errors:
        # 部分成功：保留已切出来的内容，同时记录失败块，前端可据此提示「结果不完整」
        payload["partial"] = True
        payload["failed_chunks"] = errors
    if len(chunks) > 1:
        payload.setdefault("merge", {})["chunks_total"] = len(chunks)

    raw.raw_content = {**content, "structured": payload}
    structure = payload.get("structure")
    if structure == "knowledge":
        await _persist_knowledge(
            session, datasource_id=datasource_id, raw_data_id=raw.id, payload=payload
        )
    elif structure == "summary":
        await _persist_summary(
            session,
            datasource_id=datasource_id,
            task_id=task_id,
            raw_data_id=raw.id,
            payload=payload,
        )
    await session.flush()

    logger.info(
        "media structured datasource={} type={} structure={} confidence={}",
        datasource_id,
        payload.get("content_type"),
        structure,
        payload.get("confidence"),
    )
    return payload
