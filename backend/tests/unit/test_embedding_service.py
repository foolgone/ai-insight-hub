"""B-503 嵌入服务测试（注入固定向量模型，不下载真实模型）。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import embedding_service

pytestmark = pytest.mark.unit

_DIM = settings.EMBEDDING_DIM


class _FakeModel:
    def encode(self, texts, batch_size=32, normalize_embeddings=True):  # noqa: ANN001
        return [[0.01 * (index + 1)] * _DIM for index, _ in enumerate(texts)]


def test_encode_texts_sync(monkeypatch) -> None:
    embedding_service.reset_model_cache()
    monkeypatch.setattr(embedding_service, "_get_model", lambda: _FakeModel())

    vectors = embedding_service.encode_texts_sync(["a", "b"])

    assert len(vectors) == 2
    assert all(len(vector) == _DIM for vector in vectors)


def test_encode_texts_sync_empty(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "_get_model", lambda: _FakeModel())

    assert embedding_service.encode_texts_sync([]) == []


async def test_encode_texts_async(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "_get_model", lambda: _FakeModel())

    vectors = await embedding_service.encode_texts(["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == _DIM


async def test_encode_text(monkeypatch) -> None:
    monkeypatch.setattr(embedding_service, "_get_model", lambda: _FakeModel())

    vector = await embedding_service.encode_text("hello")

    assert len(vector) == _DIM


def test_dimension_mismatch_raises(monkeypatch) -> None:
    class _BadModel:
        def encode(self, texts, batch_size=32, normalize_embeddings=True):  # noqa: ANN001
            return [[0.1] * 10 for _ in texts]

    monkeypatch.setattr(embedding_service, "_get_model", lambda: _BadModel())

    with pytest.raises(embedding_service.EmbeddingError):
        embedding_service.encode_texts_sync(["a"])


def test_reset_model_cache() -> None:
    embedding_service.reset_model_cache()
    assert embedding_service._model is None
