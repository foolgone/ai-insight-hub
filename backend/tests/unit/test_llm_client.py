"""B-200 自研 LLM 客户端单测（httpx.MockTransport，不连真实 API）。"""
from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import settings
from app.core.llm import (
    LLMAuthenticationError,
    LLMClient,
    LLMConnectionError,
    LLMContextLengthError,
    LLMError,
    LLMOverloadedError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMResponseFormatError,
    LLMServerError,
    LLMTimeoutError,
    LLMUsage,
    LLMValidationError,
)

pytestmark = pytest.mark.unit

BASE_URL = "https://llm.test/v1"
API_KEY = "test-key"


def _success(content: str = "你好", usage: tuple[int, int] = (10, 5)) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "deepseek-test",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]},
        },
    )


def _client(handler, **kwargs) -> LLMClient:
    return LLMClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        timeout=5,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def test_chat_success_parses_content_and_usage() -> None:
    async with _client(lambda request: _success("清洗结果", (120, 30))) as llm:
        resp = await llm.chat([{"role": "user", "content": "hi"}])

    assert resp.content == "清洗结果"
    assert resp.model == "deepseek-test"
    assert resp.usage == LLMUsage(input_tokens=120, output_tokens=30)
    assert resp.usage.total_tokens == 150
    assert resp.latency_ms >= 0
    assert resp.raw["choices"]


async def test_chat_builds_expected_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["_path"] = request.url.path
        captured["_auth"] = request.headers.get("authorization")
        return _success()

    async with _client(handler) as llm:
        await llm.chat(
            [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
            temperature=0.2,
            max_tokens=256,
            response_format={"type": "json_object"},
        )

    assert captured["_path"] == "/v1/chat/completions"
    assert captured["_auth"] == f"Bearer {API_KEY}"
    assert captured["model"] == settings.DEFAULT_LLM_MODEL
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 256
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"] == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]
    assert captured["stream"] is False


async def test_chat_uses_defaults_from_settings() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _success()

    async with _client(handler) as llm:
        await llm.chat([{"role": "user", "content": "hi"}])

    assert captured["temperature"] == settings.DEFAULT_TEMPERATURE
    assert captured["max_tokens"] == settings.DEFAULT_MAX_TOKENS


async def test_model_override() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _success()

    async with _client(handler) as llm:
        await llm.chat([{"role": "user", "content": "hi"}], model="degraded-model")

    assert captured["model"] == "degraded-model"


@pytest.mark.parametrize(
    ("status", "body", "expected", "retryable"),
    [
        (401, {"error": {"message": "invalid key"}}, LLMAuthenticationError, False),
        (403, {"error": {"message": "forbidden"}}, LLMAuthenticationError, False),
        (402, {"error": {"message": "insufficient balance"}}, LLMQuotaError, False),
        (429, {"error": {"message": "rate limited"}}, LLMRateLimitError, True),
        (503, {"error": {"message": "overloaded"}}, LLMOverloadedError, True),
        (500, {"error": {"message": "boom"}}, LLMServerError, True),
        (
            400,
            {"error": {"message": "maximum context length exceeded"}},
            LLMContextLengthError,
            False,
        ),
        (400, {"error": {"message": "bad param"}}, LLMValidationError, False),
        (418, {"error": {"message": "teapot"}}, LLMError, False),
    ],
)
async def test_error_mapping(status, body, expected, retryable) -> None:
    async with _client(lambda request: httpx.Response(status, json=body)) as llm:
        with pytest.raises(expected) as exc_info:
            await llm.chat([{"role": "user", "content": "hi"}])

    assert exc_info.value.status_code == status
    assert exc_info.value.retryable is retryable


async def test_timeout_maps_to_retryable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with _client(handler) as llm:
        with pytest.raises(LLMTimeoutError) as exc_info:
            await llm.chat([{"role": "user", "content": "hi"}])

    assert exc_info.value.retryable is True


async def test_connection_error_maps_to_retryable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with _client(handler) as llm:
        with pytest.raises(LLMConnectionError) as exc_info:
            await llm.chat([{"role": "user", "content": "hi"}])

    assert exc_info.value.retryable is True


async def test_malformed_response_raises_format_error() -> None:
    async with _client(lambda request: httpx.Response(200, json={"choices": []})) as llm:
        with pytest.raises(LLMResponseFormatError):
            await llm.chat([{"role": "user", "content": "hi"}])


async def test_placeholder_key_is_treated_as_unconfigured() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _success()

    llm = LLMClient(
        base_url=BASE_URL,
        api_key="your-deepseek-api-key-here",
        transport=httpx.MockTransport(handler),
    )
    assert llm.is_configured is False
    with pytest.raises(LLMAuthenticationError):
        await llm.chat([{"role": "user", "content": "hi"}])
    assert called is False


async def test_empty_key_is_treated_as_unconfigured() -> None:
    llm = LLMClient(api_key="")
    assert llm.is_configured is False


async def test_stream_yields_deltas() -> None:
    sse = (
        'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    async with _client(lambda request: httpx.Response(200, content=sse.encode())) as llm:
        chunks = [chunk async for chunk in llm.stream([{"role": "user", "content": "hi"}])]

    assert chunks == ["你", "好"]


async def test_stream_error_status_maps_to_error() -> None:
    async with _client(
        lambda request: httpx.Response(429, json={"error": {"message": "rate limited"}})
    ) as llm:
        with pytest.raises(LLMRateLimitError):
            async for _ in llm.stream([{"role": "user", "content": "hi"}]):
                pass


async def test_client_can_be_reused_and_closed() -> None:
    async with _client(lambda request: _success()) as llm:
        first = await llm.chat([{"role": "user", "content": "1"}])
        second = await llm.chat([{"role": "user", "content": "2"}])
    assert first.content == second.content == "你好"
