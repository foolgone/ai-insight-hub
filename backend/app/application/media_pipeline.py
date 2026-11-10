"""媒体（音视频）转写管线。

从 ``cleaning_service._execute_clean`` 抽出的媒体分支，职责收敛为：

- 判断 raw 是否已转写（重跑不重复计费）；
- 未转写 → 按任务归属用户解析 ASR 配置 → 转写 → 写回 ``raw.raw_content``；
- 返回 ``(records, asr 摘要)``，供上层落库与写任务结果。

**边界**：这里不碰 ``Task`` 与清洗状态机，进度通过回调上报；
调用方负责把 ``current_step`` / ``progress`` 映射到任务上。
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawData
from app.ports.asr import AsrConfig, TranscriberPort

__all__ = ["prepare_media_records"]

ProgressCallback = Callable[[str], Awaitable[None]]
#: 解析「当前用户的 ASR 配置」；由调用方注入（application 不依赖 services）
AsrResolver = Callable[[AsyncSession, uuid.UUID], Awaitable[AsrConfig]]


async def prepare_media_records(
    raw: RawData,
    *,
    session: AsyncSession,
    user_id: uuid.UUID | None,
    transcriber: TranscriberPort,
    resolve_asr: AsrResolver,
    on_progress: ProgressCallback | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """确保媒体 raw 已完成转写，返回 ``(records, asr 摘要)``。

    ``asr 摘要`` 只在本次真正调用转写时返回；已转写过的 raw 返回 ``None``。

    依赖通过参数注入（``transcriber`` / ``resolve_asr``），本模块只依赖端口，
    不 import 具体实现——换 ASR 供应商或写单测都不需要动这里。
    """
    content = raw.raw_content or {}
    asr = content.get("asr") or {}
    if asr.get("status") == "completed":
        return list(content.get("records") or []), None

    try:
        if user_id is None:
            raise ValueError("clean task has no owner")
        asr_config = await resolve_asr(session, user_id)
        transcript = await transcriber.transcribe_media(raw, asr_config, progress=on_progress)
    except Exception:
        raw.status = "failed"
        raise

    raw.raw_content = {**content, **transcript.to_dict()}
    await session.flush()
    return list(transcript.records), transcript.asr
