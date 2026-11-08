"""语音转写配置单测：协议识别、请求体、连通性校验分支。"""
from __future__ import annotations

import pytest

from app.services import asr_service
from app.services.asr_service import (
    PROTOCOL_CHAT_AUDIO,
    PROTOCOL_TRANSCRIPTIONS,
    AsrConfig,
    build_chat_audio_payload,
    detect_protocol,
)

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = "error"


class _FakeClient:
    last: dict = {}
    response: _FakeResponse = _FakeResponse(200)

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        _FakeClient.last = {"url": url, **kwargs}
        return _FakeClient.response


def test_detect_protocol_by_model() -> None:
    assert detect_protocol("qwen3-asr-flash") == PROTOCOL_CHAT_AUDIO
    assert detect_protocol("Qwen3-ASR-Flash") == PROTOCOL_CHAT_AUDIO
    assert detect_protocol("qwen-audio-asr-filetrans") == PROTOCOL_CHAT_AUDIO
    assert detect_protocol("whisper-1") == PROTOCOL_TRANSCRIPTIONS
    assert detect_protocol("FunAudioLLM/SenseVoiceSmall") == PROTOCOL_TRANSCRIPTIONS
    assert detect_protocol("") == PROTOCOL_TRANSCRIPTIONS
    assert detect_protocol(None) == PROTOCOL_TRANSCRIPTIONS


def test_endpoint_follows_protocol() -> None:
    qwen = AsrConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-x",
        model="qwen3-asr-flash",
    )
    whisper = AsrConfig(
        base_url="https://api.groq.com/openai/v1/",
        api_key="sk-x",
        model="whisper-large-v3",
    )

    assert qwen.endpoint == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert whisper.endpoint == "https://api.groq.com/openai/v1/audio/transcriptions"


def test_chat_payload_shape() -> None:
    config = AsrConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-x",
        model="qwen3-asr-flash",
        language="zh",
    )
    payload = build_chat_audio_payload(config, "data:audio/wav;base64,AAAA")

    assert payload["model"] == "qwen3-asr-flash"
    assert payload["stream"] is False
    assert payload["asr_options"] == {"enable_itn": True, "language": "zh"}
    content = payload["messages"][0]["content"][0]
    assert content["type"] == "input_audio"
    assert content["input_audio"]["data"] == "data:audio/wav;base64,AAAA"


def test_chat_payload_omits_language_for_auto() -> None:
    config = AsrConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-x",
        model="qwen3-asr-flash",
        language="auto",
    )
    payload = build_chat_audio_payload(config, "data:audio/wav;base64,AAAA")
    assert payload["asr_options"] == {"enable_itn": True}


@pytest.mark.asyncio
async def test_verify_chat_audio_uses_chat_endpoint(monkeypatch) -> None:
    _FakeClient.response = _FakeResponse(200)
    monkeypatch.setattr(asr_service.settings, "ASR_ALLOWED_HOSTS", "dashscope.aliyuncs.com")
    monkeypatch.setattr(asr_service.httpx, "AsyncClient", _FakeClient)

    config = AsrConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-x",
        model="qwen3-asr-flash",
        language="zh",
    )
    ok, reason = await asr_service.verify_config(config)

    assert ok is True
    assert reason is None
    assert _FakeClient.last["url"].endswith("/chat/completions")
    assert _FakeClient.last["json"]["model"] == "qwen3-asr-flash"


@pytest.mark.asyncio
async def test_verify_reports_invalid_key(monkeypatch) -> None:
    _FakeClient.response = _FakeResponse(401)
    monkeypatch.setattr(asr_service.settings, "ASR_ALLOWED_HOSTS", "dashscope.aliyuncs.com")
    monkeypatch.setattr(asr_service.httpx, "AsyncClient", _FakeClient)

    config = AsrConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-bad",
        model="qwen3-asr-flash",
    )
    ok, reason = await asr_service.verify_config(config)

    assert ok is False
    assert "API Key 无效" in (reason or "")


@pytest.mark.asyncio
async def test_verify_reports_wrong_endpoint(monkeypatch) -> None:
    _FakeClient.response = _FakeResponse(404)
    monkeypatch.setattr(asr_service.settings, "ASR_ALLOWED_HOSTS", "api.example.com")
    monkeypatch.setattr(asr_service.httpx, "AsyncClient", _FakeClient)

    config = AsrConfig(
        base_url="https://api.example.com/v1",
        api_key="sk-x",
        model="whisper-1",
    )
    ok, reason = await asr_service.verify_config(config)

    assert ok is False
    assert "转写接口不存在" in (reason or "")


@pytest.mark.asyncio
async def test_verify_rejects_unsafe_url(monkeypatch) -> None:
    monkeypatch.setattr(asr_service.settings, "ASR_ALLOWED_HOSTS", "")
    config = AsrConfig(
        base_url="https://127.0.0.1/v1",
        api_key="sk-x",
        model="whisper-1",
    )
    ok, reason = await asr_service.verify_config(config)

    assert ok is False
    assert "内网" in (reason or "")
