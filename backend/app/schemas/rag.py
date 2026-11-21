"""RAG 执行 Schemas（Phase 2）。

字段命名对齐评测语义：
- ``trace_id``：trace 主键（对外统一叫 trace_id）；
- ``execution_mode``：``retrieve``（纯检索）/ ``query``（Agent 问答）；
- ``execution_status``：``success`` / ``failed``；
- ``context_available``：本次是否真的拿到上下文（区分「空数组」与「未提供」）；
- ``model_config_snapshot``：避免与 Pydantic 的 ``model_config`` 冲突。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

RAGModeLiteral = Literal["retrieve", "query"]


class RagQueryRequest(BaseSchema):
    """执行一次 RAG 查询。

    - ``dataset_item_id``：从数据集条目取问题（推荐，便于追溯）；
    - 否则必须显式给 ``query``（临时调试）。
    """

    query: str | None = Field(default=None, min_length=1, max_length=10000)
    dataset_item_id: uuid.UUID | None = None
    mode: RAGModeLiteral = "query"
    adapter: str | None = Field(default=None, max_length=50)
    top_k: int | None = Field(default=None, ge=1, le=50)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_query_or_item(self) -> RagQueryRequest:
        if not self.query and self.dataset_item_id is None:
            raise ValueError("query 与 dataset_item_id 至少提供一个")
        return self


class RagContextRead(BaseSchema):
    document_id: str | None
    chunk_id: str | None
    title: str | None
    content: str
    score: float | None
    rank: int | None
    metadata: dict[str, Any]


class RagTraceRead(BaseSchema):
    trace_id: uuid.UUID
    dataset_item_id: uuid.UUID | None
    task_id: uuid.UUID | None
    adapter: str
    execution_mode: str
    context_source: str
    context_available: bool
    external_session_id: str | None
    query: str
    answer: str | None
    retrieved_contexts: list[RagContextRead]
    # 与 retrieved_contexts 平行的分数数组；外部未给 score 时为 null
    retrieved_scores: list[float | None]
    model_config_snapshot: dict[str, Any]
    retrieval_config: dict[str, Any]
    prompt_snapshot: dict[str, Any]
    latency_ms: int | None
    token_usage: dict[str, Any] | None
    missing: list[str]
    execution_status: str
    error_message: str | None
    created_at: datetime


class RagTraceListItem(BaseSchema):
    trace_id: uuid.UUID
    dataset_item_id: uuid.UUID | None
    task_id: uuid.UUID | None
    adapter: str
    execution_mode: str
    context_source: str
    context_available: bool
    query: str
    execution_status: str
    latency_ms: int | None
    context_count: int
    missing: list[str]
    created_at: datetime


class RagAdapterHealth(BaseSchema):
    adapter: str
    configured: bool
    healthy: bool
    missing: list[str] = Field(default_factory=list)
