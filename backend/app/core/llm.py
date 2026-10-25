"""自研 LLM 客户端（无框架，ADR-001）。

协议：OpenAI 兼容 ``POST {DEEPSEEK_BASE_URL}/chat/completions``
（DeepSeek 官方接口按 OpenAI 协议调用；项目不使用 LangChain / LangGraph）。

本模块只负责 4 件事（ADR-001 §6）：
1. 组装 messages 并调用模型；
2. 解析 usage（成本由调用方按 token × 单价现算，不在此处写死）；
3. 超时与错误映射（区分可重试 / 不可重试）；
4. 支持 SSE 流式读取。

不负责：重试策略（``app/utils/retry.py``）、结构化输出兜底
（``app/agents/structured_output.py``）、成本落库（``app/core/cost_tracker.py``）、
降级路由（``app/core/degradation_manager.py``）。
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings

Message = Mapping[str, str]


# --------------------------------------------------------------------------- 异常


class LLMError(Exception):
    """LLM 调用基础异常；``retryable`` 供上层重试策略判定。"""

    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        if retryable is not None:
            self.retryable = retryable


class LLMAuthenticationError(LLMError):
    """API Key 缺失、占位或无效。"""


class LLMValidationError(LLMError):
    """请求参数不合法（4xx 且非上下文/配额问题）。"""


class LLMContextLengthError(LLMError):
    """上下文超限：不重试，上层只允许截断一次。"""


class LLMQuotaError(LLMError):
    """配额/余额不足：不重试。"""


class LLMRateLimitError(LLMError):
    """限流：可重试（退避）。"""

    retryable = True


class LLMOverloadedError(LLMError):
    """服务过载/不可用：可重试。"""

    retryable = True


class LLMServerError(LLMError):
    """5xx 服务端错误：可重试。"""

    retryable = True


class LLMConnectionError(LLMError):
    """网络连接失败：可重试。"""

    retryable = True


class LLMTimeoutError(LLMError):
    """请求超时：可重试。"""

    retryable = True


class LLMResponseFormatError(LLMError):
    """响应体不是合法 JSON 结构：不重试，交由结构化输出兜底。"""


# --------------------------------------------------------------------------- 数据
@dataclass(frozen=True)
class LLMUsage:
    """token 用量（成本由调用方按单价现算）。"""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_api(cls, usage: Mapping[str, Any] | None) -> LLMUsage:
        usage = usage or {}
        return cls(
            input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        )


@dataclass(frozen=True)
class LLMResponse:
    """一次非流式调用的结果。"""

    content: str
    usage: LLMUsage
    model: str
    latency_ms: float
    raw: dict[str, Any] = field(default_factory=dict)


_CONTEXT_LENGTH_HINTS = ("context length", "context_length", "maximum context", "too long")


def _is_placeholder_key(value: str) -> bool:
    """占位 Key（如 ``your-deepseek-api-key-here``）视为未配置。"""
    return not value.strip() or value.strip().lower().startswith("your-")


# --------------------------------------------------------------------------- 客户端
class LLMClient:
    """DeepSeek（OpenAI 兼容协议）异步客户端。

    用法::

        async with LLMClient() as llm:
            resp = await llm.chat([{"role": "user", "content": "你好"}])
            print(resp.content, resp.usage.total_tokens)
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model or settings.DEFAULT_LLM_MODEL
        self._base_url = (base_url or settings.DEEPSEEK_BASE_URL).rstrip("/")
        self._api_key = settings.DEEPSEEK_API_KEY if api_key is None else api_key
        self._timeout = float(timeout if timeout is not None else settings.DEFAULT_TIMEOUT)
        self._transport = transport
        self._http: httpx.AsyncClient | None = None

    # -- 生命周期 ---------------------------------------------------------
    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        """API Key 是否可用（POC / 健康检查据此跳过真实调用）。"""
        return not _is_placeholder_key(self._api_key)

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                transport=self._transport,
            )
        return self._http

    def _headers(self) -> dict[str, str]:
        if not self.is_configured:
            raise LLMAuthenticationError("DEEPSEEK_API_KEY 未配置或仍为占位值，无法调用 LLM")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: Sequence[Message],
        *,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        response_format: Mapping[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": [dict(m) for m in messages],
            "temperature": settings.DEFAULT_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens,
            "stream": stream,
        }
        if response_format is not None:
            payload["response_format"] = dict(response_format)
        return payload

    # -- 调用 -------------------------------------------------------------
    async def chat(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        """非流式调用，返回内容 + usage。"""
        headers = self._headers()
        payload = self._build_payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=False,
        )
        started = time.perf_counter()
        try:
            response = await self._client().post("/chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"LLM 调用超时（{self._timeout}s）") from exc
        except httpx.TransportError as exc:
            raise LLMConnectionError(f"LLM 连接失败：{exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000
        self._raise_for_status(response.status_code, response.text)

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseFormatError(f"LLM 响应结构非法：{exc}") from exc

        usage = LLMUsage.from_api(data.get("usage"))
        logger.debug(
            "llm chat ok model={} tokens={} latency_ms={:.1f}",
            data.get("model", payload["model"]),
            usage.total_tokens,
            latency_ms,
        )
        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model") or payload["model"],
            latency_ms=latency_ms,
            raw=data,
        )

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """SSE 流式调用，逐个产出文本增量（usage 由 ``stream_options`` 请求，末帧返回）。"""
        headers = self._headers()
        payload = self._build_payload(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=None,
            stream=True,
        )
        payload["stream_options"] = {"include_usage": True}

        try:
            async with self._client().stream(
                "POST", "/chat/completions", json=payload, headers=headers
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    self._raise_for_status(response.status_code, body)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_raw = line[5:].strip()
                    if data_raw == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_raw)
                    except ValueError:
                        continue
                    choices = chunk.get("choices") or []
                    if choices and choices[0].get("delta", {}).get("content"):
                        yield choices[0]["delta"]["content"]
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"LLM 流式调用超时（{self._timeout}s）") from exc
        except httpx.TransportError as exc:
            raise LLMConnectionError(f"LLM 流式连接失败：{exc}") from exc

    # -- 错误映射 ---------------------------------------------------------
    def _raise_for_status(self, status_code: int, body: str) -> None:
        if status_code < 400:
            return
        detail = _extract_error_message(body)
        if status_code in (401, 403):
            raise LLMAuthenticationError(
                f"LLM 认证失败（{status_code}）：{detail}", status_code=status_code
            )
        if status_code == 402:
            raise LLMQuotaError(f"LLM 配额不足（402）：{detail}", status_code=status_code)
        if status_code == 429:
            raise LLMRateLimitError(f"LLM 限流（429）：{detail}", status_code=status_code)
        if status_code == 400:
            lowered = detail.lower()
            if any(hint in lowered for hint in _CONTEXT_LENGTH_HINTS):
                raise LLMContextLengthError(f"LLM 上下文超限：{detail}", status_code=400)
            raise LLMValidationError(f"LLM 请求不合法（400）：{detail}", status_code=400)
        if status_code == 503:
            raise LLMOverloadedError(f"LLM 服务过载（503）：{detail}", status_code=503)
        if status_code >= 500:
            raise LLMServerError(f"LLM 服务端错误（{status_code}）：{detail}", status_code=status_code)
        raise LLMError(f"LLM 调用失败（{status_code}）：{detail}", status_code=status_code)


def _extract_error_message(body: str) -> str:
    try:
        data = json.loads(body)
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or body)[:300]
    except ValueError:
        pass
    return (body or "").strip()[:300]
