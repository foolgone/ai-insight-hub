"""错误码与统一错误响应（API 设计 §3.4 / §12）。

约定：
- **业务错误码严格取自 API §12.2 的 25 条，不得自造**；
- 框架层错误（Pydantic 校验失败、未映射的路由/方法错误）使用 ``FrameworkErrorCode``，
  它们不属于业务错误码，仅用于保证错误响应结构统一；
- 统一响应体：``{"error": {"code": ..., "message": ..., "details": {...}}}``。
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(str, Enum):
    """业务错误码（API §12.2，共 25 条，不得自造）。"""

    # 401
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_REFRESH_TOKEN_INVALID = "AUTH_REFRESH_TOKEN_INVALID"
    # 403
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    # 404
    USER_NOT_FOUND = "USER_NOT_FOUND"
    DATASOURCE_NOT_FOUND = "DATASOURCE_NOT_FOUND"
    CLEANED_DATA_NOT_FOUND = "CLEANED_DATA_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    FAQ_NOT_FOUND = "FAQ_NOT_FOUND"
    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    API_KEY_NOT_FOUND = "API_KEY_NOT_FOUND"
    WEBHOOK_NOT_FOUND = "WEBHOOK_NOT_FOUND"
    # 409
    USER_EMAIL_EXISTS = "USER_EMAIL_EXISTS"
    TASK_ALREADY_RUNNING = "TASK_ALREADY_RUNNING"
    TASK_NOT_CANCELLABLE = "TASK_NOT_CANCELLABLE"
    TASK_NOT_RETRYABLE = "TASK_NOT_RETRYABLE"
    # 413 / 415
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_FORMAT_INVALID = "FILE_FORMAT_INVALID"
    # 422
    REPORT_FORMAT_INVALID = "REPORT_FORMAT_INVALID"
    # 429
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    DATASOURCE_QUOTA_EXCEEDED = "DATASOURCE_QUOTA_EXCEEDED"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    # 401 / 403（API Key，Phase 2）
    API_KEY_INVALID = "API_KEY_INVALID"
    API_KEY_SCOPE_DENIED = "API_KEY_SCOPE_DENIED"
    # 500
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FrameworkErrorCode(str, Enum):
    """框架层错误码（非业务错误码，API §12.2 未定义，仅用于统一响应结构）。"""

    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    HTTP_ERROR = "HTTP_ERROR"


ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_REFRESH_TOKEN_INVALID: 401,
    ErrorCode.API_KEY_INVALID: 401,
    ErrorCode.AUTH_FORBIDDEN: 403,
    ErrorCode.API_KEY_SCOPE_DENIED: 403,
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.DATASOURCE_NOT_FOUND: 404,
    ErrorCode.CLEANED_DATA_NOT_FOUND: 404,
    ErrorCode.TASK_NOT_FOUND: 404,
    ErrorCode.FAQ_NOT_FOUND: 404,
    ErrorCode.REPORT_NOT_FOUND: 404,
    ErrorCode.API_KEY_NOT_FOUND: 404,
    ErrorCode.WEBHOOK_NOT_FOUND: 404,
    ErrorCode.USER_EMAIL_EXISTS: 409,
    ErrorCode.TASK_ALREADY_RUNNING: 409,
    ErrorCode.TASK_NOT_CANCELLABLE: 409,
    ErrorCode.TASK_NOT_RETRYABLE: 409,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.FILE_FORMAT_INVALID: 415,
    ErrorCode.REPORT_FORMAT_INVALID: 422,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.DATASOURCE_QUOTA_EXCEEDED: 429,
    ErrorCode.INSUFFICIENT_CREDITS: 429,
    ErrorCode.INTERNAL_ERROR: 500,
}

FRAMEWORK_STATUS: dict[FrameworkErrorCode, int] = {
    FrameworkErrorCode.BAD_REQUEST: 400,
    FrameworkErrorCode.VALIDATION_ERROR: 422,
    FrameworkErrorCode.HTTP_ERROR: 404,
}


def error_payload(
    code: ErrorCode | FrameworkErrorCode | str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造统一错误响应体 ``{"error": {...}}``。"""
    code_value = code.value if isinstance(code, Enum) else str(code)
    error: dict[str, Any] = {"code": code_value, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def aiinsight_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """领域异常 → 统一错误响应。"""
    code = getattr(exc, "code", ErrorCode.INTERNAL_ERROR)
    message = getattr(exc, "message", "Internal server error")
    details = getattr(exc, "details", None)
    status_code = getattr(exc, "status_code", None) or ERROR_STATUS.get(code, 500)
    headers = getattr(exc, "headers", None)
    logger.warning("domain exception code={} status={} message={}", code, status_code, message)
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, details),
        headers=headers,
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic 请求校验失败 → 422 统一错误响应。"""
    details = {"errors": jsonable_encoder(exc.errors())}
    return JSONResponse(
        status_code=422,
        content=error_payload(
            FrameworkErrorCode.VALIDATION_ERROR, "Request validation failed", details
        ),
    )


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """框架 HTTPException（未知路由/方法）→ 尽可能映射到已知错误码。"""
    status_code = exc.status_code
    if status_code == 401:
        code: ErrorCode | FrameworkErrorCode = ErrorCode.AUTH_TOKEN_EXPIRED
        message = "Access token expired or revoked"
    elif status_code == 403:
        code = ErrorCode.AUTH_FORBIDDEN
        message = "Permission denied"
    else:
        code = FrameworkErrorCode.HTTP_ERROR
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return JSONResponse(status_code=status_code, content=error_payload(code, message))


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常 → 500 统一错误响应（不向前端泄露堆栈）。"""
    logger.opt(exception=exc).error("unhandled exception: {}", exc)
    return JSONResponse(
        status_code=500,
        content=error_payload(ErrorCode.INTERNAL_ERROR, "Internal server error"),
    )


__all__ = [
    "ERROR_STATUS",
    "FRAMEWORK_STATUS",
    "ErrorCode",
    "FrameworkErrorCode",
    "aiinsight_exception_handler",
    "error_payload",
    "http_exception_handler",
    "unhandled_exception_handler",
    "validation_exception_handler",
]
