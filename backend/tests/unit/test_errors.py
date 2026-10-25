"""B-201 错误码与统一错误响应测试。"""
from __future__ import annotations

import json

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import exceptions as exc_module
from app.core.errors import (
    ERROR_STATUS,
    ErrorCode,
    FrameworkErrorCode,
    aiinsight_exception_handler,
    error_payload,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import (
    AIInsightHubException,
    DataSourceNotFoundError,
    RateLimitExceededError,
)

pytestmark = pytest.mark.unit

BUSINESS_CODES = {
    "AUTH_INVALID_CREDENTIALS",
    "AUTH_TOKEN_EXPIRED",
    "AUTH_REFRESH_TOKEN_INVALID",
    "AUTH_FORBIDDEN",
    "USER_NOT_FOUND",
    "USER_EMAIL_EXISTS",
    "DATASOURCE_NOT_FOUND",
    "DATASOURCE_QUOTA_EXCEEDED",
    "CLEANED_DATA_NOT_FOUND",
    "FILE_TOO_LARGE",
    "FILE_FORMAT_INVALID",
    "TASK_NOT_FOUND",
    "TASK_ALREADY_RUNNING",
    "TASK_NOT_CANCELLABLE",
    "TASK_NOT_RETRYABLE",
    "FAQ_NOT_FOUND",
    "REPORT_NOT_FOUND",
    "REPORT_FORMAT_INVALID",
    "INSUFFICIENT_CREDITS",
    "RATE_LIMIT_EXCEEDED",
    "API_KEY_NOT_FOUND",
    "API_KEY_INVALID",
    "API_KEY_SCOPE_DENIED",
    "WEBHOOK_NOT_FOUND",
    "INTERNAL_ERROR",
}


def test_business_codes_match_api_design_exactly() -> None:
    assert {code.value for code in ErrorCode} == BUSINESS_CODES
    assert len(ErrorCode) == 25


def test_error_status_covers_all_business_codes() -> None:
    assert set(ERROR_STATUS) == set(ErrorCode)
    assert set(ERROR_STATUS.values()) <= {401, 403, 404, 409, 413, 415, 422, 429, 500}


def test_error_payload_shape() -> None:
    payload = error_payload(
        ErrorCode.DATASOURCE_NOT_FOUND,
        "Data source not found",
        {"datasource_id": "550e8400"},
    )
    assert payload == {
        "error": {
            "code": "DATASOURCE_NOT_FOUND",
            "message": "Data source not found",
            "details": {"datasource_id": "550e8400"},
        }
    }
    assert "details" not in error_payload(ErrorCode.INTERNAL_ERROR, "boom")


EXCEPTION_CLASSES = [name for name in sorted(exc_module.__all__) if name != "AIInsightHubException"]


@pytest.mark.parametrize("name", EXCEPTION_CLASSES)
def test_exception_classes_map_to_business_codes(name: str) -> None:
    cls = getattr(exc_module, name)
    assert issubclass(cls, AIInsightHubException)
    instance = cls()
    assert instance.code in ERROR_STATUS
    assert instance.status_code in {401, 403, 404, 409, 413, 415, 422, 429, 500}
    assert instance.message


async def test_domain_exception_handler() -> None:
    exc = DataSourceNotFoundError(details={"datasource_id": "550e8400"})
    response = await aiinsight_exception_handler(None, exc)  # type: ignore[arg-type]

    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error"]["code"] == "DATASOURCE_NOT_FOUND"
    assert body["error"]["details"] == {"datasource_id": "550e8400"}


async def test_domain_handler_keeps_headers_and_custom_status() -> None:
    exc = RateLimitExceededError(
        "Too many requests", status_code=429, headers={"Retry-After": "30"}
    )
    response = await aiinsight_exception_handler(None, exc)  # type: ignore[arg-type]

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"


async def test_validation_exception_handler() -> None:
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "email"),
                "msg": "Field required",
                "input": None,
            }
        ]
    )
    response = await validation_exception_handler(None, exc)  # type: ignore[arg-type]

    body = json.loads(response.body)
    assert response.status_code == 422
    assert body["error"]["code"] == FrameworkErrorCode.VALIDATION_ERROR.value
    assert body["error"]["details"]["errors"][0]["loc"] == ["body", "email"]


async def test_http_exception_handler_mapping() -> None:
    auth = await http_exception_handler(
        None, StarletteHTTPException(401, "Not authenticated")
    )  # type: ignore[arg-type]
    assert auth.status_code == 401
    assert json.loads(auth.body)["error"]["code"] == "AUTH_TOKEN_EXPIRED"

    forbidden = await http_exception_handler(
        None, StarletteHTTPException(403, "Forbidden")
    )  # type: ignore[arg-type]
    assert json.loads(forbidden.body)["error"]["code"] == "AUTH_FORBIDDEN"

    missing = await http_exception_handler(
        None, StarletteHTTPException(404, "Not Found")
    )  # type: ignore[arg-type]
    assert missing.status_code == 404
    assert json.loads(missing.body)["error"]["code"] == "HTTP_ERROR"


async def test_unhandled_exception_handler() -> None:
    response = await unhandled_exception_handler(None, ValueError("boom"))  # type: ignore[arg-type]

    assert response.status_code == 500
    assert json.loads(response.body)["error"]["code"] == "INTERNAL_ERROR"


def test_unknown_route_returns_unified_error(client) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"


def test_health_endpoints_still_work(client) -> None:
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/api/v1/health").json()["status"] == "healthy"
