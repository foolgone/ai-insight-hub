"""端口（Port）契约测试。

注意：``runtime_checkable`` 的 ``isinstance`` **只校验方法名存在**，
不校验签名——签名错误它照样返回 True。真正的一致性保证来自 mypy：
注入点都带 ``LLMPort`` / ``TranscriberPort`` 注解（``app/agents/base.py``、
``app/application/media_pipeline.py``），CI 的 ``mypy app`` 会校验调用方传进去的
实现是否匹配。
"""
from __future__ import annotations

import pytest

from app.core.llm import LLMClient
from app.ports import AsrConfig, LLMPort, TranscriberPort
from app.ports.asr import (
    PROTOCOL_CHAT_AUDIO,
    PROTOCOL_TRANSCRIPTIONS,
    detect_protocol,
)
from app.services import media_service

pytestmark = pytest.mark.unit


def test_llm_client_exposes_port_methods() -> None:
    """只断言方法齐备；签名一致性由 mypy 在注入点校验。"""
    client = LLMClient(model="deepseek-chat", timeout=5)
    assert isinstance(client, LLMPort)
    assert callable(client.chat)
    assert callable(client.aclose)


def test_media_module_exposes_transcriber_methods() -> None:
    assert isinstance(media_service, TranscriberPort)
    assert callable(media_service.transcribe_media)


def test_runtime_checkable_does_not_validate_signatures() -> None:
    """把这个坑固化成测试：签名完全错误的对象也会被 isinstance 判定通过。"""

    class _WrongSignature:
        def chat(self) -> None:  # 端口要求 (messages, *, model, ...) -> LLMResponse
            return None

        async def aclose(self) -> None:
            return None

    assert isinstance(_WrongSignature(), LLMPort)


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
