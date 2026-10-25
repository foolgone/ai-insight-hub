"""B-316 降级中间件集成测试（正常头 / STOPPED 429 / 豁免路径）。"""
from __future__ import annotations

import pytest

from app.core.degradation import DegradationLevel
from app.core.degradation_manager import DegradationManager
from app.middleware.degradation_middleware import EXEMPT_PATHS

pytestmark = pytest.mark.integration


def _patch_ratio(monkeypatch, ratio: float) -> None:
    async def _fake(self, *, user_id=None):  # noqa: ANN001
        return ratio

    monkeypatch.setattr(DegradationManager, "get_cost_ratio", _fake)


async def test_normal_request_exposes_cost_headers(client, auth_headers, monkeypatch) -> None:
    _patch_ratio(monkeypatch, 0.25)

    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["X-Cost-Status"] == DegradationLevel.NORMAL.value
    assert response.headers["X-Cost-Usage"] == "25.00%"
    assert response.headers["X-Cost-Reset"].isdigit()


async def test_warning_level_is_reflected_in_headers(client, auth_headers, monkeypatch) -> None:
    _patch_ratio(monkeypatch, 0.85)

    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["X-Cost-Status"] == DegradationLevel.WARNING.value


async def test_stopped_level_returns_429(client, auth_headers, monkeypatch) -> None:
    _patch_ratio(monkeypatch, 1.5)

    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "INSUFFICIENT_CREDITS"
    assert response.headers["X-Cost-Status"] == DegradationLevel.STOPPED.value
    assert response.headers["Retry-After"] == "3600"


async def test_exempt_paths_bypass_degradation(client, monkeypatch) -> None:
    _patch_ratio(monkeypatch, 1.5)

    for path in ("/health", "/metrics"):
        response = await client.get(path)
        assert response.status_code == 200
        assert "X-Cost-Status" not in response.headers


async def test_anonymous_request_skips_cost_check(client, monkeypatch) -> None:
    _patch_ratio(monkeypatch, 1.5)

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert "/api/v1/health" not in EXEMPT_PATHS
    assert "X-Cost-Status" not in response.headers
