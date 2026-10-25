"""POC 公共设施：仅在 ``tests/poc`` 下使用，不进入主 CI。

- 真实 LLM 调用依赖 ``DEEPSEEK_API_KEY`` 与 ``LLM_PRICE_*``，未配置时自动 skip；
- 向量 POC 依赖本地 PostgreSQL 14 + pgvector（``DATABASE_URL``）与 sentence-transformers；
- 显式运行：``pytest tests/poc -v -s``（``pytest.ini`` 的 norecursedirs 已排除本目录）。
"""
from __future__ import annotations

import pytest

from app.core.config import settings


def database_dsn() -> str:
    """把 SQLAlchemy 连接串转成 asyncpg 可用的 DSN。"""
    return settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql").replace(
        "postgresql+psycopg2", "postgresql"
    )


def skip_without_llm() -> None:
    from app.core.llm import LLMClient

    if not LLMClient().is_configured:
        pytest.skip("DEEPSEEK_API_KEY 未配置或仍为占位值，跳过真实 LLM 调用（POC 报告记为待验证）")


def skip_without_embedding_model() -> None:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:  # pragma: no cover - 取决于本地环境
        pytest.skip("sentence-transformers 未安装，跳过向量质量 POC（性能 POC 仍可运行）")
