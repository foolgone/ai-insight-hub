"""端口（Port）契约测试：确保具体实现始终满足 Protocol。

这层测试的价值：把「可替换性」变成可验证的事实。实现方只要签名漂移，
这里会立刻失败，而不是等到某天换供应商时才发现业务代码被写死。
"""
from __future__ import annotations

import pytest

from app.core.llm import LLMClient
from app.ports import AsrConfig, LLMPort, StoragePort, TranscriberPort
from app.ports.asr import (
    PROTOCOL_CHAT_AUDIO,
    PROTOCOL_TRANSCRIPTIONS,
    detect_protocol,
)
from app.services import media_service, storage_service

pytestmark = pytest.mark.unit


def test_llm_client_satisfies_port() -> None:
    client = LLMClient(model="deepseek-chat", timeout=5)
    assert isinstance(client, LLMPort)


def test_storage_module_satisfies_port() -> None:
    # 模块级函数实现：模块对象本身即满足协议，无需包一层类
    assert isinstance(storage_service, StoragePort)
    for name in ("save_upload", "read_upload", "save_bytes", "read_bytes"):
        assert callable(getattr(storage_service, name))


def test_media_module_satisfies_transcriber_port() -> None:
    assert isinstance(media_service, TranscriberPort)
    assert callable(getattr(media_service, "transcribe_media"))


def test_asr_protocol_detection_moved_to_ports() -> None:
    assert detect_protocol("qwen3-asr-flash") == PROTOCOL_CHAT_AUDIO
    assert detect_protocol("whisper-1") == PROTOCOL_TRANSCRIPTIONS
    assert detect_protocol(None) == PROTOCOL_TRANSCRIPTIONS


def test_asr_config_endpoint_follows_protocol() -> None:
    chat = AsrConfig(base_url="https://api.example.com/v1/", api_key="k", model="qwen3-asr-flash")
    assert chat.endpoint == "https://api.example.com/v1/chat/completions"

    standard = AsrConfig(base_url="https://api.example.com/v1", api_key="k", model="whisper-1")
    assert standard.endpoint == "https://api.example.com/v1/audio/transcriptions"


def test_asr_service_reexports_config_for_compat() -> None:
    """老代码 ``from app.services.asr_service import AsrConfig`` 必须继续可用。"""
    from app.services import asr_service

    assert asr_service.AsrConfig is AsrConfig
    assert asr_service.detect_protocol is detect_protocol
