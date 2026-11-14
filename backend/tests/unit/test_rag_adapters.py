"""RAG 适配器单测（Phase 2）。

全部通过 ``httpx.MockTransport`` 构造响应，不访问网络、不使用真实密钥。
覆盖：正常检索/问答、空结果、缺 answer、超时、非 2xx、SSE 正常/截断/错误事件、
重试边界（429 重试后成功 / 重试耗尽）。
"""
from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.ports.rag import RAGResult
from app.services.rag.mock import MockRAGAdapter
from app.services.rag.weknora import WeKnoraAdapter, WeKnoraError

pytestmark = pytest.mark.unit


def _adapter(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_retries: int = 1,
    api_key: str = "test-key",
) -> WeKnoraAdapter:
    return WeKnoraAdapter(
        base_url="http://weknora.test",
        api_key=api_key,
        agent_id="agent-1",
        kb_id="kb-1",
        tenant_id="10000",
        timeout=2.0,
        max_retries=max_retries,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _json_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=data)


# --------------------------------------------------------------------------- retrieve


async def test_retrieve_maps_contexts_and_marks_missing_score() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/knowledge-bases/kb-1/hybrid-search"
        assert request.headers["X-API-Key"] == "test-key"
        assert request.headers["X-Tenant-ID"] == "10000"
        body = json.loads(request.content)
        assert body["query_text"] == "怎么退款"
        assert body["match_count"] == 5
        return _json_response(
            {
                "success": True,
                "data": [
                    {
                        "knowledge_id": "k-1",
                        "knowledge_title": "退款说明",
                        "content": "在订单页申请退款。",
                    }
                ],
            }
        )

    adapter = _adapter(handler)
    result = await adapter.retrieve("怎么退款", config={"top_k": 5})
    await adapter.aclose()

    assert result.mode == "retrieve"
    assert result.context_source == "hybrid_search"
    assert len(result.contexts) == 1
    context = result.contexts[0]
    assert context.document_id == "k-1"
    assert context.title == "退款说明"
    assert context.content == "在订单页申请退款。"
    assert context.score is None
    assert "score" in result.missing
    assert "token_usage" in result.missing
    assert result.raw is not None


async def test_retrieve_empty_result_is_success() -> None:
    adapter = _adapter(lambda request: _json_response({"success": True, "data": []}))
    result = await adapter.retrieve("没有命中")
    await adapter.aclose()

    assert result.contexts == ()
    assert result.context_source == "hybrid_search"
    assert "token_usage" in result.missing


# --------------------------------------------------------------------------- query


def _chat_handler(payload: dict) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/sessions":
            return _json_response({"data": {"id": "session-1"}})
        assert request.url.path == "/api/v1/agent-chat/session-1"
        return _json_response(payload)

    return handler


async def test_query_parses_json_answer_and_contexts() -> None:
    adapter = _adapter(
        _chat_handler(
            {
                "data": {
                    "answer": "提交退款申请后 1-3 天到账。",
                    "results": [
                        {
                            "knowledge_id": "k-1",
                            "chunk_id": "c-1",
                            "content": "退款 1-3 天到账",
                            "score": 0.77,
                        }
                    ],
                }
            }
        )
    )
    result = await adapter.query("退款多久到账")
    await adapter.aclose()

    assert result.mode == "query"
    assert result.context_source == "agent_chat"
    assert result.answer == "提交退款申请后 1-3 天到账。"
    assert result.external_session_id == "session-1"
    assert len(result.contexts) == 1
    assert result.contexts[0].score == 0.77


async def test_query_without_contexts_marks_none() -> None:
    """Agent 未返回上下文：必须标 none，不能借用 hybrid-search 结果。"""
    adapter = _adapter(_chat_handler({"data": {"answer": "只有答案"}}))
    result = await adapter.query("问题")
    await adapter.aclose()

    assert result.answer == "只有答案"
    assert result.contexts == ()
    assert result.context_source == "none"
    assert "retrieved_contexts" in result.missing


async def test_query_missing_answer() -> None:
    adapter = _adapter(_chat_handler({"data": {}}))
    result = await adapter.query("问题")
    await adapter.aclose()

    assert result.answer is None
    assert "answer" in result.missing


# --------------------------------------------------------------------------- SSE


SSE_OK = "\n".join(
    [
        "event: message",
        'data: {"response_type":"answer","content":"根据"}',
        "",
        "event: message",
        'data: {"response_type":"answer","content":"知识片段，"}',
        "",
        "event: message",
        (
            'data: {"response_type":"tool_result","data":{"results":'
            '[{"knowledge_id":"k-1","content":"退款 1-3 天","chunk_id":"c-1"}]}}'
        ),
        "",
        "event: message",
        "data: [DONE]",
        "",
    ]
)

SSE_TRUNCATED = "\n".join(
    [
        'data: {"response_type":"answer","content":"前半段"}',
        "",
        'data: {"response_type":"answer","content":"断',
    ]
)


def _sse_handler(raw: str) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/sessions":
            return _json_response({"data": {"id": "session-sse"}})
        return httpx.Response(200, text=raw, headers={"content-type": "text/event-stream"})

    return handler


async def test_sse_parses_answer_and_contexts() -> None:
    adapter = _adapter(_sse_handler(SSE_OK))
    result = await adapter.query("退款")
    await adapter.aclose()

    assert result.answer == "根据知识片段，"
    assert len(result.contexts) == 1
    assert result.contexts[0].document_id == "k-1"
    assert result.context_source == "agent_chat"


SSE_REFERENCES = "\n".join(
    [
        'data: {"response_type":"references","knowledge_references":'
        '[{"id":"chunk-ref-1","knowledge_id":"doc-ref-1","content":"退款 1-3 天",'
        '"knowledge_title":"售后政策","score":0.88,"seq":0,"chunk_type":"text"}]}',
        "",
        'data: {"response_type":"answer","content":"退款 1-3 天"}',
        "",
        "data: [DONE]",
        "",
    ]
)


async def test_sse_parses_knowledge_references_event() -> None:
    """WeKnora >= 0.9 的检索片段在 references 事件，不在 tool_result.data.results。"""
    adapter = _adapter(_sse_handler(SSE_REFERENCES))
    result = await adapter.query("退款")
    await adapter.aclose()

    assert result.context_source == "agent_chat"
    assert len(result.contexts) == 1
    context = result.contexts[0]
    assert context.document_id == "doc-ref-1"
    assert context.chunk_id == "chunk-ref-1"
    assert context.title == "售后政策"
    assert context.score == 0.88
    assert context.metadata["chunk_type"] == "text"


async def test_sse_truncated_midstream_keeps_received_content() -> None:
    """中途断开：保留已收到的答案，不抛异常（残缺事件被忽略）。"""
    adapter = _adapter(_sse_handler(SSE_TRUNCATED))
    result = await adapter.query("退款")
    await adapter.aclose()

    assert result.answer == "前半段"
    assert result.context_source == "none"


async def test_sse_error_event_raises() -> None:
    raw = "\n".join(
        [
            'data: {"response_type":"error","content":"模型超时"}',
            "",
        ]
    )
    adapter = _adapter(_sse_handler(raw))
    with pytest.raises(WeKnoraError):
        await adapter.query("退款")
    await adapter.aclose()


# --------------------------------------------------------------------------- 错误与重试


async def test_http_error_is_raised_without_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, text="boom")

    adapter = _adapter(handler, max_retries=2)
    with pytest.raises(WeKnoraError) as excinfo:
        await adapter.retrieve("问题")
    await adapter.aclose()

    assert "HTTP 500" in str(excinfo.value)
    assert calls["n"] == 1


async def test_retry_on_429_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, text="slow down")
        return _json_response({"success": True, "data": []})

    adapter = _adapter(handler, max_retries=2)
    result = await adapter.retrieve("问题")
    await adapter.aclose()

    assert result.contexts == ()
    assert calls["n"] == 3


async def test_retry_exhausted_raises() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="unavailable")

    adapter = _adapter(handler, max_retries=2)
    with pytest.raises(WeKnoraError):
        await adapter.retrieve("问题")
    await adapter.aclose()

    assert calls["n"] == 3


async def test_timeout_raises_after_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timeout", request=request)

    adapter = _adapter(handler, max_retries=1)
    with pytest.raises(WeKnoraError) as excinfo:
        await adapter.retrieve("问题")
    await adapter.aclose()

    assert "ReadTimeout" in str(excinfo.value)
    assert calls["n"] == 2


async def test_health_check_false_without_config() -> None:
    adapter = WeKnoraAdapter(base_url="", api_key="", client=httpx.AsyncClient())
    assert await adapter.health_check() is False
    await adapter.aclose()


async def test_health_check_true_when_reachable() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, text="ok"))
    assert await adapter.health_check() is True
    await adapter.aclose()


# --------------------------------------------------------------------------- Mock


async def test_mock_adapter_is_deterministic_and_marked() -> None:
    adapter = MockRAGAdapter()

    first = await adapter.retrieve("怎么退款")
    second = await adapter.retrieve("怎么退款")
    answer = await adapter.query("怎么退款")

    assert isinstance(first, RAGResult)
    assert first.contexts == second.contexts
    assert first.retrieval_config["mock"] is True
    assert answer.model_config["mock"] is True
    assert answer.context_source == "agent_chat"
    assert answer.answer is not None
    assert "token_usage" in answer.missing
