"""WeKnora 适配器（Phase 2）。

只做「协议翻译」：把外部返回的 JSON / SSE 映射为 ``RAGResult``，并如实记录缺失字段。
不在这里算指标、不落库。

接口契约来自外部既有脚本的实测（不复制其密钥）：
- ``POST {base}/api/v1/sessions``                     建会话 → ``data.id``
- ``POST {base}/api/v1/agent-chat/{session_id}``      端到端问答（可能返回 SSE）
- ``POST {base}/api/v1/knowledge-bases/{kb}/hybrid-search``  纯检索 → ``data[]``

SSE 事件：``response_type ∈ agent_query/tool_call/tool_result/answer/complete``；
答案由 ``answer`` 事件按字符分片流式下发，检索片段在 ``tool_result.data.results``。
"""
from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.core.config import settings
from app.ports.rag import RAGResult, RetrievedContext

DEFAULT_MAX_CONTEXT_CHARS = 4000
MAX_RAW_CHARS = 200_000
_RETRY_STATUS = {429, 502, 503, 504}


class WeKnoraError(RuntimeError):
    """外部服务不可用或响应不符合契约。"""


class WeKnoraAdapter:
    """WeKnora 适配器（一个实例复用一个 httpx client）。"""

    name = "weknora"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        agent_id: str | None = None,
        kb_id: str | None = None,
        tenant_id: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.WEKNORA_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.WEKNORA_API_KEY
        self.agent_id = agent_id or settings.WEKNORA_AGENT_ID
        self.kb_id = kb_id or settings.WEKNORA_KB_ID
        self.tenant_id = tenant_id or settings.WEKNORA_TENANT_ID
        self.timeout = float(timeout if timeout is not None else settings.RAG_TIMEOUT_SECONDS)
        self.max_retries = int(max_retries if max_retries is not None else settings.RAG_MAX_RETRIES)
        self._client = client or httpx.AsyncClient(timeout=self.timeout)

    # ------------------------------------------------------------------ 生命周期

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def missing_settings(self) -> list[str]:
        missing = []
        if not self.base_url:
            missing.append("WEKNORA_BASE_URL")
        if not self.api_key:
            missing.append("WEKNORA_API_KEY")
        return missing

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ 对外能力

    async def retrieve(self, query: str, *, config: Mapping[str, Any] | None = None) -> RAGResult:
        # 评测 Run 会显式传入 knowledge_base_id（配置快照，保证重试可复现）；
        # 普通调用不传时回退环境配置。
        kb_id = str((config or {}).get("knowledge_base_id") or self.kb_id or "")
        if not kb_id:
            raise WeKnoraError("缺少 WEKNORA_KB_ID，无法执行纯检索")
        payload = {
            "query_text": query,
            "match_count": int((config or {}).get("top_k") or 10),
            "vector_threshold": float((config or {}).get("vector_threshold") or 0.0),
            "keyword_threshold": float((config or {}).get("keyword_threshold") or 0.0),
        }
        started = time.perf_counter()
        raw = await self._request(
            "POST",
            f"/api/v1/knowledge-bases/{kb_id}/hybrid-search",
            payload=payload,
            extra_headers={"X-Tenant-ID": self.tenant_id} if self.tenant_id else None,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        if not raw.get("success", True):
            raise WeKnoraError(f"hybrid-search 失败: {str(raw.get('error'))[:200]}")

        items = raw.get("data") or []
        contexts, missing = self._map_search_items(items)
        return RAGResult(
            query=query,
            mode="retrieve",
            contexts=contexts,
            latency_ms=latency_ms,
            context_source="hybrid_search",
            model_config={},
            retrieval_config=payload,
            token_usage=None,
            raw=self._truncate_raw(raw),
            missing=tuple(dict.fromkeys(["token_usage", *missing])),
        )

    async def query(self, query: str, *, config: Mapping[str, Any] | None = None) -> RAGResult:
        agent_id = str((config or {}).get("agent_id") or self.agent_id or "")
        if not agent_id:
            raise WeKnoraError("缺少 WEKNORA_AGENT_ID，无法执行端到端问答")
        started = time.perf_counter()
        session = await self._request(
            "POST",
            "/api/v1/sessions",
            payload={"title": "rag-eval", "description": "RAG 评测"},
        )
        session_id = (session.get("data") or {}).get("id")
        if not session_id:
            raise WeKnoraError(f"建会话响应缺少 data.id: {str(session)[:200]}")

        payload = {"query": query, "agent_enabled": True, "agent_id": agent_id}
        raw_text = await self._request_text(
            "POST", f"/api/v1/agent-chat/{session_id}", payload=payload
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        parsed, events = self._parse_payload(raw_text)
        if parsed is not None and parsed.get("success") is False:
            raise WeKnoraError(f"agent-chat 失败: {str(parsed.get('error'))[:200]}")
        for event in events:
            if event.get("response_type") == "error":
                raise WeKnoraError(f"SSE 错误事件: {str(event.get('content') or event)[:200]}")
        answer = self._extract_answer(parsed, events)
        contexts, missing = self._extract_contexts(parsed, events)

        if answer is None:
            missing.append("answer")
        if not contexts:
            missing.append("retrieved_contexts")

        return RAGResult(
            query=query,
            mode="query",
            contexts=contexts,
            latency_ms=latency_ms,
            # 关键：端到端问答的上下文只能来自本次生成；拿不到就标记 none
            context_source="agent_chat" if contexts else "none",
            answer=answer,
            external_session_id=str(session_id),
            model_config={"agent_id": agent_id},
            retrieval_config={"agent_enabled": True},
            token_usage=self._extract_token_usage(parsed),
            raw=self._truncate_raw(raw_text),
            missing=tuple(dict.fromkeys(["token_usage", *missing])),
        )

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            response = await self._client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code < 500
        except Exception:  # noqa: BLE001 - 健康检查不抛异常
            return False

    # ------------------------------------------------------------------ HTTP

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"X-API-Key": self.api_key or ""}
        if extra:
            headers.update({key: value for key, value in extra.items() if value})
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        text = await self._request_text(method, path, payload=payload, extra_headers=extra_headers)
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise WeKnoraError(f"响应不是 JSON: {text[:200]}") from exc
        if not isinstance(parsed, dict):
            raise WeKnoraError("响应 JSON 不是对象")
        return parsed

    async def _request_text(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> str:
        url = f"{self.base_url}{path}"
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    json=payload,
                    headers=self._headers(extra_headers),
                )
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries:
                    await self._sleep(attempt)
                    continue
                raise WeKnoraError(last_error) from exc

            if response.status_code in _RETRY_STATUS and attempt < self.max_retries:
                last_error = f"HTTP {response.status_code}"
                await self._sleep(attempt)
                continue
            if response.status_code >= 400:
                raise WeKnoraError(f"HTTP {response.status_code}: {response.text[:300]}")
            return response.text

        raise WeKnoraError(last_error or "unknown error")

    async def _sleep(self, attempt: int) -> None:
        import asyncio

        await asyncio.sleep(min(2.0, 0.3 * (attempt + 1)))

    # ------------------------------------------------------------------ 解析

    @staticmethod
    def _parse_payload(raw_text: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """返回 ``(JSON 响应, SSE 事件列表)``；两者必有一个为空。"""
        try:
            payload = json.loads(raw_text)
        except ValueError:
            return None, WeKnoraAdapter._parse_sse(raw_text)
        if isinstance(payload, dict):
            return payload, []
        return None, []

    @staticmethod
    def _parse_sse(raw_text: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        data_lines: list[str] = []
        for line in raw_text.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif not line.strip() and data_lines:
                chunk = "\n".join(data_lines)
                data_lines = []
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    events.append(json.loads(chunk))
                except ValueError:
                    continue
        if data_lines:
            chunk = "\n".join(data_lines)
            if chunk and chunk != "[DONE]":
                try:
                    events.append(json.loads(chunk))
                except ValueError:
                    pass
        return events

    @staticmethod
    def _extract_answer(
        payload: Mapping[str, Any] | None, events: Sequence[Mapping[str, Any]]
    ) -> str | None:
        if events:
            fragments = [
                str(event.get("content") or "")
                for event in events
                if event.get("response_type") == "answer"
            ]
            joined = "".join(fragments).strip()
            return WeKnoraAdapter._clean_answer(joined) if joined else None
        if not payload:
            return None
        candidates = (
            ("data", "reply"),
            ("reply",),
            ("data", "answer"),
            ("answer",),
            ("data", "content"),
            ("content",),
            ("result",),
            ("output",),
        )
        for path in candidates:
            value: Any = payload
            for key in path:
                value = value.get(key) if isinstance(value, Mapping) else None
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _clean_answer(text: str) -> str:
        """剥掉 markdown 代码围栏 / 结构化 JSON 外壳，取可读回复。"""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        if cleaned.startswith("{"):
            try:
                obj = json.loads(cleaned)
                for key in ("reply", "answer", "content", "text", "output"):
                    if isinstance(obj.get(key), str) and obj[key].strip():
                        return obj[key].strip()
            except ValueError:
                pass
        return cleaned.strip()

    def _extract_contexts(
        self, payload: Mapping[str, Any] | None, events: Sequence[Mapping[str, Any]]
    ) -> tuple[tuple[RetrievedContext, ...], list[str]]:
        items: list[Mapping[str, Any]] = []
        missing: list[str] = []
        for event in events:
            if event.get("response_type") != "tool_result":
                continue
            data = event.get("data") or {}
            results = data.get("results") if isinstance(data, Mapping) else None
            if isinstance(results, list):
                items.extend(item for item in results if isinstance(item, Mapping))
        if not items and payload:
            for key in (
                "results",
                "citations",
                "references",
                "contexts",
                "knowledge_chunks",
                "retrieved",
            ):
                value = payload.get(key)
                if value is None and isinstance(payload.get("data"), Mapping):
                    data_obj = payload["data"]
                value = data_obj.get(key)
                if isinstance(value, list):
                    items.extend(item for item in value if isinstance(item, Mapping))
                    break
        return self._map_contexts(items, missing)

    def _map_search_items(
        self, items: Sequence[Mapping[str, Any]]
    ) -> tuple[tuple[RetrievedContext, ...], list[str]]:
        return self._map_contexts(items, [])

    def _map_contexts(
        self, items: Sequence[Mapping[str, Any]], missing: list[str]
    ) -> tuple[tuple[RetrievedContext, ...], list[str]]:
        contexts: list[RetrievedContext] = []
        if not items:
            return tuple(contexts), missing
        for rank, item in enumerate(items, start=1):
            content = self._first_text(item, ("content", "text", "chunk", "knowledge"))
            truncated = False
            if content and len(content) > DEFAULT_MAX_CONTEXT_CHARS:
                content = content[:DEFAULT_MAX_CONTEXT_CHARS]
                truncated = True
            if not content:
                missing.append("contexts.content")
            score = self._first_number(item, ("score", "similarity", "relevance_score"))
            if score is None:
                missing.append("score")
            contexts.append(
                RetrievedContext(
                    content=content or "",
                    document_id=self._first_text(item, ("knowledge_id", "document_id", "doc_id")),
                    chunk_id=self._first_text(item, ("chunk_id", "chunkId")),
                    title=self._first_text(item, ("knowledge_title", "title", "doc_name")),
                    score=score,
                    rank=rank,
                    metadata={
                        "knowledge_base_id": item.get("knowledge_base_id"),
                        "truncated": truncated,
                    },
                )
            )
        return tuple(contexts), missing

    @staticmethod
    def _first_text(item: Mapping[str, Any], keys: Sequence[str]) -> str | None:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _first_number(item: Mapping[str, Any], keys: Sequence[str]) -> float | None:
        for key in keys:
            value = item.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @staticmethod
    def _extract_token_usage(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not payload:
            return None
        for key in ("usage", "token_usage"):
            value = payload.get(key)
            if isinstance(value, Mapping):
                return dict(value)
        data = payload.get("data")
        if isinstance(data, Mapping):
            for key in ("usage", "token_usage"):
                value = data.get(key)
                if isinstance(value, Mapping):
                    return dict(value)
        return None

    @staticmethod
    def _truncate_raw(raw: Mapping[str, Any] | str) -> Mapping[str, Any] | str:
        if isinstance(raw, str):
            return raw[:MAX_RAW_CHARS]
        text = json.dumps(raw, ensure_ascii=False)
        if len(text) <= MAX_RAW_CHARS:
            return raw
        return {"truncated": True, "preview": text[:MAX_RAW_CHARS]}


__all__ = ["DEFAULT_MAX_CONTEXT_CHARS", "WeKnoraAdapter", "WeKnoraError"]
