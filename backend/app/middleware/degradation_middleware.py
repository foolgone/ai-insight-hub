"""降级中间件（B-316；06-成本超限降级策略 §3.4）。

- 已认证请求：按当日成本判定等级，响应头写 ``X-Cost-Usage`` / ``X-Cost-Status`` / ``X-Cost-Reset``；
- ``STOPPED``：直接返回 429（``INSUFFICIENT_CREDITS``），不进入业务处理（禁止抛 HTTPException）；
- 豁免路径：``/health``、``/metrics``、``/docs``、``/openapi.json``、``/redoc``；
- 未携带 Bearer Token 的请求跳过成本判定（由后续鉴权返回 401），避免匿名请求查库。

D-09：``DEGRADED_LLM_MODEL`` 留空时只降级告警、不切换模型（模型选择不在中间件里做）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.database import SessionLocal
from app.core.degradation import DegradationLevel, level_for_ratio
from app.core.degradation_manager import DegradationManager
from app.core.errors import ErrorCode, error_payload
from app.core.security import decode_token

EXEMPT_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


def _user_id_from_request(request: Request) -> uuid.UUID | None:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, "access")
        return uuid.UUID(str(payload["sub"]))
    except Exception:  # noqa: BLE001 - 未认证/无效 token 交给后续鉴权处理
        return None


def _cost_headers(level: DegradationLevel, ratio: float) -> dict[str, str]:
    tomorrow = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    return {
        "X-Cost-Usage": f"{ratio * 100:.2f}%",
        "X-Cost-Status": level.value,
        "X-Cost-Reset": str(int(tomorrow.timestamp())),
    }


class DegradationMiddleware(BaseHTTPMiddleware):
    """按当日成本做请求级降级拦截。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        user_id = _user_id_from_request(request)
        if user_id is None:
            return await call_next(request)

        async with SessionLocal() as session:
            ratio = await DegradationManager(session).get_cost_ratio(user_id=user_id)
        level = level_for_ratio(ratio)
        headers = _cost_headers(level, ratio)

        if DegradationManager.is_service_stopped(level):
            headers["Retry-After"] = "3600"
            return JSONResponse(
                status_code=429,
                content=error_payload(
                    ErrorCode.INSUFFICIENT_CREDITS,
                    "Daily cost limit reached; AI features are temporarily disabled",
                ),
                headers=headers,
            )

        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response


__all__ = ["EXEMPT_PATHS", "DegradationMiddleware"]
