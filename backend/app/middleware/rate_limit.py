"""限流中间件（API 设计 §1.1、§12.3）。

- 固定窗口：Redis 计数 ``ratelimit:{client}:{window}``，窗口 60s；
- 超限返回 429 + ``X-RateLimit-*`` / ``Retry-After`` 头；
- 探活/文档/指标端点豁免（避免监控被限流）。
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.errors import ErrorCode, error_payload
from app.core.redis import get_redis

EXEMPT_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 Redis 的固定窗口限流。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.RATE_LIMIT_ENABLED or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        key = f"ratelimit:{client}:{window}"
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)

        limit = settings.RATE_LIMIT_PER_MINUTE
        reset_at = (window + 1) * 60
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, limit - count)),
            "X-RateLimit-Reset": str(reset_at),
        }

        if count > limit:
            headers["Retry-After"] = str(max(1, reset_at - int(time.time())))
            return JSONResponse(
                status_code=429,
                content=error_payload(ErrorCode.RATE_LIMIT_EXCEEDED, "Too many requests"),
                headers=headers,
            )

        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response


__all__ = ["EXEMPT_PATHS", "RateLimitMiddleware"]
