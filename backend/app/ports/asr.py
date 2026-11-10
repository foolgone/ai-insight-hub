"""语音转写端口：协议识别 + 转写配置 + 转写接口。

这里只放**纯数据与纯逻辑**（不碰数据库、不发请求），所以端口层不依赖
``app.services``；真正的 I/O（解析用户配置、连通性校验、调用 ASR）留在
``app.services.asr_service`` / ``app.services.media_service``。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

PROTOCOL_TRANSCRIPTIONS = "transcriptions"
PROTOCOL_CHAT_AUDIO = "chat_audio"

# 千问系列走 chat/completions + input_audio（不返回时间戳）
_CHAT_AUDIO_MODEL_PREFIXES = ("qwen3-asr", "qwen-audio-asr", "qwen2-audio")


def detect_protocol(model: str | None) -> str:
    """按模型名判断接口协议；未知模型一律按标准 transcriptions 处理。"""
    name = (model or "").strip().lower()
    if name.startswith(_CHAT_AUDIO_MODEL_PREFIXES):
        return PROTOCOL_CHAT_AUDIO
    return PROTOCOL_TRANSCRIPTIONS


@dataclass(frozen=True)
class AsrConfig:
    """一次转写所需的完整配置（明文 Key 只在内存中）。"""

    base_url: str
    api_key: str
    model: str
    language: str | None = None
    # 留空则按 model 自动识别，调用方无需关心
    protocol: str = ""

    @property
    def effective_protocol(self) -> str:
        return self.protocol or detect_protocol(self.model)

    @property
    def endpoint(self) -> str:
        path = (
            "/chat/completions"
            if self.effective_protocol == PROTOCOL_CHAT_AUDIO
            else "/audio/transcriptions"
        )
        return f"{self.base_url.rstrip('/')}{path}"


@runtime_checkable
class TranscriberPort(Protocol):
    """转写接口。

    实现方：``app.services.media_service``（模块对象，含 ``transcribe_media``）。
    返回写回 ``raw_content`` 的字段字典（``transcript`` / ``segments`` / ``channel_mode`` 等）。
    """

    async def transcribe_media(
        self,
        raw: Any,
        asr: AsrConfig,
        *,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        ...


__all__ = [
    "AsrConfig",
    "PROTOCOL_CHAT_AUDIO",
    "PROTOCOL_TRANSCRIPTIONS",
    "TranscriberPort",
    "detect_protocol",
]
