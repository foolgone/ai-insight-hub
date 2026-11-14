"""RAG 适配器工厂。

- ``mock``：确定性适配器（默认，无外部依赖）；
- ``weknora``：外部服务（需要 ``WEKNORA_*`` 环境变量）。

新增适配器只在这里登记，业务 service 不感知具体实现。
"""
from __future__ import annotations

from app.core.config import settings
from app.core.errors import FrameworkErrorCode
from app.core.exceptions import AIInsightHubException
from app.ports.rag import RAGPort
from app.services.rag.mock import MockRAGAdapter
from app.services.rag.weknora import WeKnoraAdapter

SUPPORTED_ADAPTERS = ("mock", "weknora")


def build_adapter(name: str | None = None, *, require_configured: bool = True) -> RAGPort:
    """按名称构造适配器；未知名称 → 400（不静默回退，避免误用 mock 当真实结果）。"""
    resolved = (name or settings.RAG_ADAPTER or "mock").strip().lower()
    if resolved == "mock":
        return MockRAGAdapter()
    if resolved == "weknora":
        adapter = WeKnoraAdapter()
        if require_configured and not adapter.configured:
            raise AIInsightHubException(
                "WeKnora 适配器未配置（缺少 WEKNORA_BASE_URL / WEKNORA_API_KEY）",
                code=FrameworkErrorCode.BAD_REQUEST,
                status_code=400,
                details={"adapter": "weknora", "missing": adapter.missing_settings()},
            )
        return adapter
    raise AIInsightHubException(
        f"不支持的 RAG 适配器：{resolved}",
        code=FrameworkErrorCode.BAD_REQUEST,
        status_code=400,
        details={"adapter": resolved, "supported": list(SUPPORTED_ADAPTERS)},
    )


__all__ = ["SUPPORTED_ADAPTERS", "build_adapter"]
