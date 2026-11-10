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


@dataclass(frozen=True)
class Transcript:
    """转写结果（顶层结构类型化，避免「魔法 key」耦合）。

    ``records`` 内部仍是字典（那是下游 schema 的事），但顶层字段不再靠约定。
    """

    text: str
    records: list[dict[str, Any]]
    media: dict[str, Any]
    asr: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """写回 ``raw_content`` 时用的字典形态（与历史数据结构保持一致）。"""
        return {
            "text": self.text,
            "media": self.media,
            "asr": self.asr,
            "records": self.records,
        }


@runtime_checkable
class TranscriberPort(Protocol):
    """转写接口。

    实现方：``app.services.media_service``（模块对象，含 ``transcribe_media``）。
    """

    async def transcribe_media(
        self,
        raw: Any,
        asr: AsrConfig,
        *,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> Transcript:
        ...


__all__ = [
    "AsrConfig",
    "PROTOCOL_CHAT_AUDIO",
    "PROTOCOL_TRANSCRIPTIONS",
    "Transcript",
    "TranscriberPort",
    "detect_protocol",
]
