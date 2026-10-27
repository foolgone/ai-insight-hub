"""知识提取成本优化：对话规则去重 + 既有问题语义选优（T9 Phase 1）。

设计要点：
- 纯函数优先（``normalize_text`` / ``dedupe_dialogues`` / ``expand_source_ids`` /
  ``estimate_prompt_savings``），便于单测；
- 语义选优 ``select_relevant_questions`` 依赖 pgvector 与本地 embedding，
  **任何异常都 fail-open**（回退到旧行为），不阻塞提取任务；
- 去重只合并「问题与答案归一化后完全相同」的对话，不做语义合并（语义聚类留 Phase 2）。
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase
from app.services import embedding_service

_WHITESPACE = re.compile(r"[\s\u3000]+")
_TRAILING_PUNCT = re.compile(r"[。！？!?.,，;；:：\s]+$")
_TOKEN_CHARS_RATIO = 1.6  # 中文混合场景的粗略估算：字符数 ÷ 1.6 ≈ token


def normalize_text(text: str) -> str:
    """归一化文本：NFKC + casefold + 合并空白 + 去尾部标点。"""
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.casefold()
    value = _WHITESPACE.sub(" ", value).strip()
    return _TRAILING_PUNCT.sub("", value)


def dedupe_dialogues(
    dialogues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, dict[str, list[str]]]:
    """合并完全重复的问答对（问题 + 答案归一化后都相同）。

    Returns:
        (去重后对话列表, 移除条数, 代表 dialogue_id -> 全部 dialogue_id)
        - 保留首次出现（调用方按时间倒序加载，因此代表即最新一条）；
        - 代表对话增加 ``duplicate_count`` 字段，供 prompt 频次判断；
        - ``dialogue_id`` 缺失的对话仍参与去重，但不进映射表。
    """
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    deduped: list[dict[str, Any]] = []
    id_map: dict[str, list[str]] = {}

    for item in dialogues:
        key = (
            normalize_text(str(item.get("user_message", ""))),
            normalize_text(str(item.get("ai_response", ""))),
        )
        dialogue_id = str(item.get("dialogue_id") or "").strip()

        existing = seen.get(key)
        if existing is not None:
            existing["duplicate_count"] = int(existing.get("duplicate_count", 1)) + 1
            if dialogue_id:
                rep_id = str(existing.get("dialogue_id") or "").strip()
                if rep_id:
                    ids = id_map.setdefault(rep_id, [rep_id])
                    if dialogue_id not in ids:
                        ids.append(dialogue_id)
            continue

        entry = dict(item)
        entry["duplicate_count"] = 1
        seen[key] = entry
        deduped.append(entry)
        if dialogue_id:
            id_map[dialogue_id] = [dialogue_id]

    return deduped, len(dialogues) - len(deduped), id_map


def expand_source_ids(faqs: list[dict[str, Any]], id_map: dict[str, list[str]]) -> int:
    """把 FAQ 的 source_dialogue_ids 从「代表 id」展开为「同簇全部 id」。

    Returns:
        实际发生展开的 FAQ 条数。
    """
    if not id_map:
        return 0

    expanded = 0
    for faq in faqs:
        raw_ids = [str(item) for item in (faq.get("source_dialogue_ids") or [])]
        merged: list[str] = []
        for source_id in raw_ids:
            for candidate in id_map.get(source_id, [source_id]):
                if candidate and candidate not in merged:
                    merged.append(candidate)
        if len(merged) > len({item for item in raw_ids if item}):
            expanded += 1
        faq["source_dialogue_ids"] = merged
    return expanded


def dialogue_query_text(dialogues: list[dict[str, Any]], max_chars: int = 800) -> str:
    """把对话的用户问题拼成用于检索既有 FAQ 的查询文本（截断到 max_chars）。"""
    if max_chars <= 0:
        return ""
    parts: list[str] = []
    total = 0
    for item in dialogues:
        text = str(item.get("user_message", "")).strip()
        if not text:
            continue
        parts.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return " ".join(parts)[:max_chars]


def estimate_prompt_savings(
    *,
    deduped_dialogues: list[dict[str, Any]],
    removed_dialogues: int,
    legacy_questions: list[str],
    sent_questions: list[str],
) -> tuple[int, int]:
    """估算去重 + 语义选优可节省的 prompt 字符数 / token 数（仅用于趋势观测）。"""
    if deduped_dialogues:
        avg_dialogue_chars = sum(
            len(str(item.get("user_message", ""))) + len(str(item.get("ai_response", ""))) + 40
            for item in deduped_dialogues
        ) / len(deduped_dialogues)
    else:
        avg_dialogue_chars = 0.0

    legacy_sample = legacy_questions[:30]
    avg_question_chars = (
        sum(len(str(item)) + 20 for item in legacy_sample) / len(legacy_sample)
        if legacy_sample
        else 0.0
    )
    removed_questions = max(0, len(legacy_sample) - len(sent_questions))

    chars_saved = int(
        removed_dialogues * avg_dialogue_chars + removed_questions * avg_question_chars
    )
    return chars_saved, int(chars_saved / _TOKEN_CHARS_RATIO)


async def select_relevant_questions(
    session: AsyncSession | None,
    *,
    datasource_id: uuid.UUID,
    dialogues: list[dict[str, Any]],
    legacy_questions: list[str],
    top_k: int,
    query_chars: int = 800,
) -> tuple[list[str], str, str | None]:
    """按「当前对话」语义选最相关的既有 FAQ 问题。

    Returns:
        (问题列表, 模式, 失败原因)
        模式：``embedding_topk`` / ``legacy_top30`` / ``fallback``

    设计为 fail-open：embedding 不可用（离线/模型缺失）、无候选、top_k<=0 时，
    均回退为旧行为（把全部既有问题交给 Agent 截前 30 条），不阻塞提取。
    """
    if top_k <= 0:
        return list(legacy_questions), "legacy_top30", None
    if not legacy_questions:
        return [], "embedding_topk", None
    if session is None:
        return list(legacy_questions), "fallback", "no_session"

    query = dialogue_query_text(dialogues, max_chars=query_chars)
    if not query:
        return list(legacy_questions), "fallback", "no_query_text"

    try:
        vectors = await embedding_service.encode_texts([query])
        if not vectors or not vectors[0]:
            return list(legacy_questions), "fallback", "empty_embedding"
        stmt = (
            select(KnowledgeBase.question)
            .where(
                KnowledgeBase.datasource_id == datasource_id,
                KnowledgeBase.is_seed.is_(False),
                KnowledgeBase.embedding.is_not(None),
            )
            .order_by(KnowledgeBase.embedding.cosine_distance(vectors[0]))
            .limit(top_k)
        )
        rows = (await session.execute(stmt)).scalars().all()
        questions = [str(item) for item in rows]
        if not questions:
            return list(legacy_questions), "fallback", "no_candidates_with_embedding"
        return questions, "embedding_topk", None
    except Exception as exc:  # noqa: BLE001 - 语义选优失败不阻塞提取
        logger.warning("existing questions semantic selection failed: {}", exc)
        return list(legacy_questions), "fallback", f"{type(exc).__name__}: {exc}"[:200]


__all__ = [
    "dedupe_dialogues",
    "dialogue_query_text",
    "estimate_prompt_savings",
    "expand_source_ids",
    "normalize_text",
    "select_relevant_questions",
]
