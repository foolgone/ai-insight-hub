"""B-212 路由聚合与 OpenAPI 契约测试。"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

EXPECTED_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/users/me",
    "/api/v1/users/me/password",
    "/api/v1/datasources",
    "/api/v1/datasources/{datasource_id}",
    "/api/v1/datasources/{datasource_id}/upload",
    "/api/v1/datasources/{datasource_id}/clean",
    "/api/v1/datasources/{datasource_id}/cleaned-data",
    "/api/v1/datasources/{datasource_id}/cleaned-data/{data_id}",
    "/api/v1/datasources/{datasource_id}/analyze/quality",
    "/api/v1/datasources/{datasource_id}/analysis/quality",
    "/api/v1/datasources/{datasource_id}/analysis/quality/{result_id}/review",
    "/api/v1/datasources/{datasource_id}/extract-knowledge",
    "/api/v1/datasources/{datasource_id}/knowledge/faq",
    "/api/v1/datasources/{datasource_id}/knowledge/faq/{faq_id}",
    "/api/v1/datasources/{datasource_id}/knowledge/search",
    "/api/v1/datasources/{datasource_id}/knowledge/gaps",
    "/api/v1/datasources/{datasource_id}/reports",
    "/api/v1/reports/{report_id}",
    "/api/v1/reports/{report_id}/download",
    "/api/v1/tasks",
    "/api/v1/tasks/{task_id}",
    "/api/v1/tasks/{task_id}/cancel",
    "/api/v1/tasks/{task_id}/retry",
    "/health",
}


async def test_openapi_exposes_current_endpoints(client) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert EXPECTED_PATHS <= paths


async def test_metrics_endpoint_available(client) -> None:
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "llm_calls_total" in response.text


async def test_health_check_payload(client) -> None:
    response = await client.get("/api/v1/health")

    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "ai-insight-hub-api"
    assert "version" in body
