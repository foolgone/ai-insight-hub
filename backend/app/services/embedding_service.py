"""嵌入服务（B-503；Agent 详细设计 §4.2）。

- 模型：sentence-transformers 多语言 MiniLM（默认 384 维，与 ``Vector(384)`` 一致）；
- 批量编码 + L2 归一化（pgvector cosine 检索）；
- 同步/异步双入口：异步走线程池，避免阻塞事件循环；
- 离线部署：``EMBEDDING_CACHE_DIR`` 指向本地模型目录（避免联网下载）。

单测通过 monkeypatch ``_get_model`` 注入固定向量模型，不触发模型下载。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from app.core.config import settings


class EmbeddingError(Exception):
    """嵌入模型加载或维度异常（不可重试）。"""

    retryable = False


_model: Any | None = None
_model_error: Exception | None = None


def _resolved_cache_dir() -> str | None:
    """模型缓存目录：优先配置值；为空时自动探测镜像内默认目录。"""
    configured = settings.EMBEDDING_CACHE_DIR.strip()
    if configured:
        return configured
    default = Path("/app/.models")
    if default.is_dir():
        return str(default)
    return None


def _get_model():  # noqa: ANN202 - 返回 SentenceTransformer 或测试替身
    global _model, _model_error
    if _model is None:
        # 失败缓存：避免每条文本都重新尝试加载/联网（离线环境尤为重要）
        if _model_error is not None:
            raise EmbeddingError(f"embedding model unavailable: {_model_error}") from _model_error
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - 依赖缺失时明确报错
            _model_error = exc
            raise EmbeddingError("sentence-transformers is not installed") from exc
        kwargs: dict[str, Any] = {"device": settings.EMBEDDING_DEVICE}
        cache_dir = _resolved_cache_dir()
        if cache_dir:
            kwargs["cache_folder"] = cache_dir
        try:
            _model = SentenceTransformer(settings.EMBEDDING_MODEL, **kwargs)
        except Exception as exc:  # noqa: BLE001 - 网络/磁盘/模型异常统一收敛
            _model_error = exc
            raise EmbeddingError(f"failed to load embedding model: {exc}") from exc
    return _model


def reset_model_cache() -> None:
    """释放模型缓存（测试/模型切换/恢复后重试用）。"""
    global _model, _model_error
    _model = None
    _model_error = None


def _offline_enabled() -> bool:
    return os.environ.get("HF_HUB_OFFLINE", "").lower() in ("1", "true", "yes")


def _has_local_model() -> bool:
    """判断本地缓存目录里是否已有模型文件（不触发加载）。"""
    cache_dir = _resolved_cache_dir()
    if not cache_dir:
        return False
    root = Path(cache_dir)
    if not root.is_dir():
        return False
    # 兼容两种布局：直接目录（config.json）与 HF cache（models--*/snapshots/*/config.json）
    return any(root.rglob("config.json"))


def model_status() -> dict[str, Any]:
    """嵌入模型状态（供 /health 使用，不触发模型加载）。"""
    base = {
        "model": settings.EMBEDDING_MODEL,
        "cache_dir": _resolved_cache_dir(),
        "offline": _offline_enabled(),
    }
    if _model is not None:
        return {**base, "ready": True, "loaded": True}
    if _model_error is not None:
        return {**base, "ready": False, "loaded": False, "error": str(_model_error)[:500]}
    return {**base, "ready": _has_local_model(), "loaded": False}


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
    "model_status",
    "reset_model_cache",
]
