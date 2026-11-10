"""语音转写配置（BYOK）：解析用户配置 + 保存前连通性校验。

配置来自用户在「语音转写设置」里填写的内容（密文存 ``user_llm_credentials``，
``provider='asr'``），**不再读 ``.env``**。``.env`` 只保留 ops 级旋钮
（开关、超时、切片、重试、单价、SSRF 白名单）。

支持两种接口协议（按模型名自动识别）：
- ``transcriptions``：OpenAI 标准 ``POST /audio/transcriptions``（multipart 文件），
  返回 ``text`` + ``segments``（有时间戳）；
- ``chat_audio``：千问 Qwen3-ASR 的 OpenAI 兼容形态
  ``POST /chat/completions`` + ``input_audio``（base64 Data URI），
  **不返回时间戳**，按切片偏移量构造粗粒度 segment。
"""
from __future__ import annotations

import base64
import io
import math
import struct
import uuid
import wave

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AsrCredentialInvalidError, AsrCredentialNotConfiguredError
from app.core.url_guard import UnsafeUrlError, assert_safe_base_url
from app.ports.asr import (
    PROTOCOL_CHAT_AUDIO,
    PROTOCOL_TRANSCRIPTIONS,
    AsrConfig,
    detect_protocol,
)
from app.services.credential_service import PROVIDER_ASR, credential_service

__all__ = [
    "AsrConfig",
    "DEFAULT_ASR_LANGUAGE",
    "DEFAULT_ASR_MODEL",
    "PROTOCOL_CHAT_AUDIO",
    "PROTOCOL_TRANSCRIPTIONS",
    "detect_protocol",
    "resolve_for_user",
    "verify_config",
]

DEFAULT_ASR_MODEL = "whisper-1"
DEFAULT_ASR_LANGUAGE = "zh"
SUPPORTED_LANGUAGES = {"zh", "en", "ja", "ko", "yue", "auto"}


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
        protocol=detect_protocol(row.model),
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


def build_chat_audio_payload(config: AsrConfig, data_uri: str) -> dict:
    """千问 chat/completions 请求体（``asr_options`` 是非标准参数，放顶层）。"""
    payload: dict = {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "input_audio", "input_audio": {"data": data_uri}}],
            }
        ],
        "stream": False,
    }
    asr_options: dict = {"enable_itn": True}
    if config.language and config.language != "auto":
        asr_options["language"] = config.language
    payload["asr_options"] = asr_options
    return payload


async def verify_config(config: AsrConfig) -> tuple[bool, str | None]:
    """真调一次转写接口（1 秒音频）：返回 (是否可用, 失败原因)。"""
    try:
        assert_safe_base_url(config.base_url)
    except UnsafeUrlError as exc:
        return False, str(exc)

    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        async with httpx.AsyncClient(timeout=min(settings.ASR_TIMEOUT, 60)) as client:
            if config.effective_protocol == PROTOCOL_CHAT_AUDIO:
                data_uri = "data:audio/wav;base64," + base64.b64encode(_probe_wav()).decode()
                response = await client.post(
                    config.endpoint,
                    headers=headers,
                    json=build_chat_audio_payload(config, data_uri),
                )
            else:
                payload = {"model": config.model, "response_format": "json"}
                if config.language and config.language != "auto":
                    payload["language"] = config.language
                response = await client.post(
                    config.endpoint,
                    headers=headers,
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
    if response.status_code == 404:
        return False, "转写接口不存在（请检查服务地址与模型名是否匹配）"
    return False, f"转写服务返回 {response.status_code}：{response.text[:200]}"
