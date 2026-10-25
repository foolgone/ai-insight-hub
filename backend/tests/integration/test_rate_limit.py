"""B-211 限流中间件集成测试（真实 Redis）。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.redis import get_redis

pytestmark = pytest.mark.integration


async def _clear_rate_limit_keys() -> None:
    redis = get_redis()
    async for key in redis.scan_iter("ratelimit:*"):
        await redis.delete(key)


async def test_rate_limit_returns_429_with_headers(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    await _clear_rate_limit_keys()

    first = await client.get("/api/v1/health")
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert first.headers["X-RateLimit-Remaining"] == "1"

    second = await client.get("/api/v1/health")
    assert second.status_code == 200
    assert second.headers["X-RateLimit-Remaining"] == "0"

    third = await client.get("/api/v1/health")
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert third.headers["X-RateLimit-Remaining"] == "0"
    assert "X-RateLimit-Reset" in third.headers
    assert int(third.headers["Retry-After"]) >= 1

    await _clear_rate_limit_keys()


async def test_exempt_health_path_is_not_limited(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    await _clear_rate_limit_keys()

    for _ in range(3):
        response = await client.get("/health")
        assert response.status_code == 200

    await _clear_rate_limit_keys()


async def test_rate_limit_disabled_passes_through(client) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
