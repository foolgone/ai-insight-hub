"""embedding_service 离线化相关单测（不加载真实模型）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services import embedding_service

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_model_cache():
    embedding_service.reset_model_cache()
    yield
    embedding_service.reset_model_cache()


def test_model_status_not_ready_without_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_CACHE_DIR", str(tmp_path))

    status = embedding_service.model_status()

    assert status["ready"] is False
    assert status["loaded"] is False
    assert status["cache_dir"] == str(tmp_path)


def test_model_status_ready_when_model_files_exist(tmp_path: Path, monkeypatch) -> None:
    snapshot = tmp_path / "models--x" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "EMBEDDING_CACHE_DIR", str(tmp_path))

    status = embedding_service.model_status()

    assert status["ready"] is True
    assert status["loaded"] is False


def test_load_failure_is_cached(monkeypatch) -> None:
    """首次加载失败后不再重复尝试（避免每条文本都联网/重试）。"""
    import sentence_transformers

    calls: list[int] = []

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(1)
        raise RuntimeError("model download failed")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", _boom)

    with pytest.raises(embedding_service.EmbeddingError):
        embedding_service.encode_texts_sync(["第一条"])
    with pytest.raises(embedding_service.EmbeddingError):
        embedding_service.encode_texts_sync(["第二条"])

    assert len(calls) == 1
    assert embedding_service.model_status()["ready"] is False
    assert "model download failed" in (embedding_service.model_status()["error"] or "")


def test_reset_model_cache_clears_failure(monkeypatch) -> None:
    import sentence_transformers

    monkeypatch.setattr(
        sentence_transformers,
        "SentenceTransformer",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(embedding_service.EmbeddingError):
        embedding_service.encode_texts_sync(["x"])

    embedding_service.reset_model_cache()

    assert embedding_service.model_status().get("error") is None
