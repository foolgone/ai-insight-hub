"""嵌入服务（B-503；Agent 详细设计 §4.2）。

- 模型：sentence-transformers 多语言 MiniLM（默认 384 维，与 ``Vector(384)`` 一致）；
- 批量编码 + L2 归一化（pgvector cosine 检索）；
- 同步/异步双入口：异步走线程池，避免阻塞事件循环；
- 离线部署：``EMBEDDING_CACHE_DIR`` 指向本地模型目录（避免联网下载）。

单测通过 monkeypatch ``_get_model`` 注入固定向量模型，不触发模型下载。
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings


class EmbeddingError(Exception):
    """嵌入模型加载或维度异常（不可重试）。"""

    retryable = False


_model: Any | None = None


def _get_model():  # noqa: ANN202 - 返回 SentenceTransformer 或测试替身
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - 依赖缺失时明确报错
            raise EmbeddingError("sentence-transformers is not installed") from exc
        kwargs: dict[str, Any] = {"device": settings.EMBEDDING_DEVICE}
        if settings.EMBEDDING_CACHE_DIR:
            kwargs["cache_folder"] = settings.EMBEDDING_CACHE_DIR
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, **kwargs)
    return _model


def reset_model_cache() -> None:
    """释放模型缓存（测试/模型切换用）。"""
    global _model
    _model = None


def _encode_batch(texts: list[str], batch_size: int | None) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(
        list(texts),
        batch_size=batch_size or settings.EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
    )
    result: list[list[float]] = []
    for vector in vectors:
        values = [float(item) for item in vector]
        if len(values) != settings.EMBEDDING_DIM:
            raise EmbeddingError(
                f"embedding dimension mismatch: {len(values)} != " f"{settings.EMBEDDING_DIM}"
            )
        result.append(values)
    return result


def encode_texts_sync(texts: list[str], *, batch_size: int | None = None) -> list[list[float]]:
    """同步批量编码（agent 的同步校验阶段使用）。"""
    if not texts:
        return []
    return _encode_batch(texts, batch_size)


async def encode_texts(texts: list[str], *, batch_size: int | None = None) -> list[list[float]]:
    """异步批量编码（服务层使用，线程池执行）。"""
    if not texts:
        return []
    return await asyncio.to_thread(_encode_batch, texts, batch_size)


async def encode_text(text: str) -> list[float]:
    vectors = await encode_texts([text])
    return vectors[0]


__all__ = [
    "EmbeddingError",
    "encode_text",
    "encode_texts",
    "encode_texts_sync",
    "reset_model_cache",
]
