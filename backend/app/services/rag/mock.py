"""Mock RAG 适配器（Phase 2）。

用途：
- 无外部凭据时跑通「查询 → trace → 指标」链路（CI / 本地 / 演示）；
- 作为 ``RAGPort`` 的契约测试基准。

**必须可识别**：``model_config={"mock": true}``，trace 上 ``adapter="mock"``。
Mock 的结果不得出现在任何「真实评测结论」里（Phase 3 的报告会标注 adapter）。
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from app.ports.rag import RAGResult, RetrievedContext

MOCK_DOC_ID = "mock-doc-approval"
MOCK_CHUNK_ID = "mock-chunk-approval-1"


class MockRAGAdapter:
    """确定性适配器：同一 query 永远返回同一结果，便于断言。"""

    name = "mock"

    def __init__(self, *, latency_ms: int = 5) -> None:
        self._latency_ms = latency_ms

    async def retrieve(self, query: str, *, config: Mapping[str, Any] | None = None) -> RAGResult:
        started = time.perf_counter()
        top_k = int((config or {}).get("top_k") or 3)
        contexts = self._contexts()[:top_k]
        return RAGResult(
            query=query,
            mode="retrieve",
            contexts=contexts,
            latency_ms=max(self._latency_ms, int((time.perf_counter() - started) * 1000)),
            context_source="hybrid_search",
            retrieval_config={"top_k": top_k, "mock": True},
            raw={
                "success": True,
                "data": [self._raw_item(index) for index in range(len(contexts))],
            },
            # Mock 不产生 token；显式标注缺失，避免被当成 0
            missing=("token_usage",),
        )

    async def query(self, query: str, *, config: Mapping[str, Any] | None = None) -> RAGResult:
        started = time.perf_counter()
        contexts = self._contexts()
        answer = f"[mock] 根据知识片段，关于「{query}」的处理方式是：提交申请后由审批人确认。"
        return RAGResult(
            query=query,
            mode="query",
            contexts=contexts,
            latency_ms=max(self._latency_ms, int((time.perf_counter() - started) * 1000)),
            context_source="agent_chat",
            answer=answer,
            external_session_id="mock-session",
            model_config={"mock": True, "model": "mock-rag"},
            retrieval_config={"top_k": len(contexts), "mock": True},
            prompt_snapshot={"mock": True},
            raw={"success": True, "answer": answer, "data": {"results": [self._raw_item(0)]}},
            missing=("token_usage",),
        )

    async def health_check(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    @staticmethod
    def _contexts() -> tuple[RetrievedContext, ...]:
        return (
            RetrievedContext(
                content="提交退款申请后，审批人在 1 个工作日内确认，确认后原路退回。",
                document_id=MOCK_DOC_ID,
                chunk_id=MOCK_CHUNK_ID,
                title="售后审批说明（mock）",
                score=0.92,
                rank=1,
                metadata={"mock": True},
            ),
            RetrievedContext(
                content="审批未通过时，系统会展示拒绝原因，可修改后重新提交。",
                document_id=MOCK_DOC_ID,
                chunk_id="mock-chunk-approval-2",
                title="售后审批说明（mock）",
                score=0.81,
                rank=2,
                metadata={"mock": True},
            ),
            RetrievedContext(
                content="发票在订单完成后 24 小时内自动开具，可在订单详情下载。",
                document_id="mock-doc-invoice",
                chunk_id="mock-chunk-invoice-1",
                title="发票说明（mock）",
                score=0.42,
                rank=3,
                metadata={"mock": True},
            ),
        )

    @staticmethod
    def _raw_item(index: int) -> dict[str, Any]:
        return {
            "knowledge_id": MOCK_DOC_ID,
            "chunk_id": f"mock-chunk-{index + 1}",
            "knowledge_title": "售后审批说明（mock）",
            "content": "mock 片段内容",
            "score": 0.9 - index * 0.1,
        }


__all__ = ["MOCK_CHUNK_ID", "MOCK_DOC_ID", "MockRAGAdapter"]
