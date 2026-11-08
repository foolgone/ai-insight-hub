"""语音转写配置（BYOK）：解析用户配置 + 保存前连通性校验。

配置来自用户在「语音转写设置」里填写的内容（密文存 ``user_llm_credentials``，
``provider='asr'``），**不再读 ``.env``**。``.env`` 只保留 ops 级旋钮
（开关、超时、切片、重试、单价、SSRF 白名单）。
"""
from __future__ import annotations

import io
import math
import struct
import uuid
import wave
from dataclasses import dataclass

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AsrCredentialInvalidError, AsrCredentialNotConfiguredError
from app.core.url_guard import UnsafeUrlError, assert_safe_base_url
from app.services.credential_service import PROVIDER_ASR, credential_service

__all__ = [
    "AsrConfig",
    "DEFAULT_ASR_MODEL",
    "DEFAULT_ASR_LANGUAGE",
    "resolve_for_user",
    "verify_config",
]

DEFAULT_ASR_MODEL = "whisper-1"
DEFAULT_ASR_LANGUAGE = "zh"
SUPPORTED_LANGUAGES = {"zh", "en", "ja", "ko", "yue", "auto"}


@dataclass(frozen=True)
class AsrConfig:
    """一次转写所需的完整配置（明文 Key 只在内存中）。"""

    base_url: str
    api_key: str
    model: str
    language: str | None = None

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/audio/transcriptions"


async def resolve_for_user(session: AsyncSession, user_id: uuid.UUID) -> AsrConfig:
    """取用户 ASR 配置；功能关闭/未配置 → 428，已失效 → 400。"""
    if not settings.ASR_ENABLED:
        raise AsrCredentialNotConfiguredError("语音转写功能已关闭（ASR_ENABLED=false）")
    row = await credential_service.get_credential(session, user_id, PROVIDER_ASR)
    if row is None:
        raise AsrCredentialNotConfiguredError()
    if row.status != "active":
        raise AsrCredentialInvalidError()
    if not row.base_url or not row.model:
        raise AsrCredentialNotConfiguredError("语音转写配置不完整，请重新填写")
    return AsrConfig(
        base_url=row.base_url,
        api_key=credential_service.decrypt_credential(row),
        model=row.model,
        language=row.language or DEFAULT_ASR_LANGUAGE,
    )


def _probe_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    """生成一段低音量正弦波 WAV，用于保存前的连通性校验（不依赖 ffmpeg）。"""
    amplitude = 1200
    frames = bytearray()
    for index in range(int(rate * seconds)):
        value = int(amplitude * math.sin(2 * math.pi * 440 * index / rate))
        frames += struct.pack("<h", value)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


async def verify_config(config: AsrConfig) -> tuple[bool, str | None]:
    """真调一次 ``/audio/transcriptions``（1 秒音频）：返回 (是否可用, 失败原因)。"""
    try:
        assert_safe_base_url(config.base_url)
    except UnsafeUrlError as exc:
        return False, str(exc)

    payload = {
        "model": config.model,
        "response_format": "json",
    }
    if config.language and config.language != "auto":
        payload["language"] = config.language

    try:
        async with httpx.AsyncClient(timeout=min(settings.ASR_TIMEOUT, 60)) as client:
            response = await client.post(
                config.endpoint,
                headers={"Authorization": f"Bearer {config.api_key}"},
                data=payload,
                files={"file": ("probe.wav", _probe_wav(), "audio/wav")},
            )
    except httpx.HTTPError as exc:
        logger.info("asr verify network error base_url={} error={}", config.base_url, exc)
        return False, f"无法连接转写服务：{exc}"

    if 200 <= response.status_code < 300:
        return True, None
    if response.status_code in (401, 403):
        return False, "API Key 无效或无权限"
    return False, f"转写服务返回 {response.status_code}：{response.text[:200]}"
