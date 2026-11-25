"""API 依赖：当前用户、RBAC、租户上下文。

- ``get_token_payload``：解析 ``Authorization: Bearer <access>`` 并检查黑名单；
- ``get_current_user``：加载用户、校验 tenant claim、解析 X-Tenant-Id（platform_admin）；
- ``require_roles``：角色白名单（platform_admin / tenant_admin / user / viewer）。
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    LLMCredentialInvalidError,
    LLMCredentialNotConfiguredError,
    PermissionDeniedError,
    TenantNotFoundError,
    TokenExpiredError,
    UserNotFoundError,
)
from app.core.pagination import PaginationParams
from app.core.redis import is_token_blacklisted
from app.core.security import decode_token
from app.core.tenancy import (
    TenantContext,
    attach_tenant_context,
)
from app.models import AuditLog, Tenant, User
from app.services.credential_service import credential_service


async def get_token_payload(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """解析并校验 access token（缺失/无效/已吊销 → 401 AUTH_TOKEN_EXPIRED）。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise TokenExpiredError("Missing access token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, "access")
    if await is_token_blacklisted(str(payload["jti"])):
        raise TokenExpiredError("Access token revoked")
    return payload


async def get_current_user(
    request: Request,
    payload: dict = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> User:
    """当前登录用户 + 租户上下文。"""
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:  # pragma: no cover - 已由 decode_token 保证
        raise TokenExpiredError("Invalid token subject") from exc

    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise UserNotFoundError()
    if not user.is_active:
        raise PermissionDeniedError("User is inactive")

    _verify_tenant_claim(payload, user)
    if not settings.TENANT_ENFORCEMENT_ENABLED:
        # flag=false：仍解析 context 供写入使用，但不做跨租户拒绝。
        context = TenantContext(
            tenant_id=user.tenant_id,
            enforced=False,
            is_platform_admin=user.role == "platform_admin",
            actor_user_id=user.id,
        )
        attach_tenant_context(user, context)
        return user

    target_tenant_id = user.tenant_id
    requested_tenant_id = None
    if user.role == "platform_admin" and x_tenant_id:
        try:
            requested_tenant_id = uuid.UUID(x_tenant_id)
        except ValueError as exc:
            raise TenantNotFoundError(details={"tenant_id": x_tenant_id}) from exc
        tenant = await session.get(Tenant, requested_tenant_id)
        if (
            tenant is None
            or tenant.status != "active"
            or getattr(tenant, "kind", "customer") != "customer"
        ):
            raise TenantNotFoundError(details={"tenant_id": x_tenant_id})
        target_tenant_id = tenant.id

    context = TenantContext(
        tenant_id=target_tenant_id,
        enforced=True,
        is_platform_admin=user.role == "platform_admin",
        actor_user_id=user.id,
        requested_tenant_id=requested_tenant_id,
    )
    attach_tenant_context(user, context)

    if requested_tenant_id is not None and requested_tenant_id != user.tenant_id:
        session.add(
            AuditLog(
                user_id=user.id,
                tenant_id=requested_tenant_id,
                action="tenant.cross_access",
                resource_type="tenant",
                resource_id=requested_tenant_id,
                details={
                    "actor_tenant_id": str(user.tenant_id),
                    "target_tenant_id": str(requested_tenant_id),
                    "method": request.method,
                    "path": request.url.path,
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        )
        await session.flush()
    return user


def _verify_tenant_claim(payload: dict, user: User) -> None:
    """校验 JWT tenant claim；旧 token 在 grace 期内按 DB 租户解析。"""
    claim = payload.get("tenant_id")
    if claim is not None:
        try:
            claim_tenant_id = uuid.UUID(str(claim))
        except ValueError as exc:
            raise TokenExpiredError("Invalid tenant claim") from exc
        if claim_tenant_id != user.tenant_id:
            raise TokenExpiredError("Tenant claim mismatch")
        return
    issued_at = payload.get("iat")
    if issued_at is None:
        raise TokenExpiredError("Missing tenant claim")
    try:
        issued = datetime.fromtimestamp(float(issued_at), tz=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise TokenExpiredError("Invalid token issued-at") from exc
    if datetime.now(timezone.utc) - issued > timedelta(days=settings.TENANT_CLAIM_GRACE_DAYS):
        raise TokenExpiredError("Tenant claim grace period expired; re-login")


def require_roles(*roles: str) -> Callable:
    """生成角色校验依赖；角色不足 → 403 AUTH_FORBIDDEN。"""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("Insufficient role")
        return user

    return dependency


async def require_llm_credential(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    """BYOK 守门（AI 触发端点专用）。

    - ``ALLOW_SERVER_KEY_FALLBACK=true``（开发/CI）→ 放行，行为与现状一致；
    - 无凭据 → 428 ``LLM_CREDENTIAL_NOT_CONFIGURED``（不入队、不发 LLM）；
    - 凭据已标记 invalid → 400 ``LLM_CREDENTIAL_INVALID``（引导更新）。
    """
    if settings.ALLOW_SERVER_KEY_FALLBACK:
        return user
    credential = await credential_service.get_credential(session, user.id)
    if credential is None:
        raise LLMCredentialNotConfiguredError()
    if credential.status != "active":
        raise LLMCredentialInvalidError()
    return user


async def pagination_params(
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    limit: int = Query(20, ge=1, le=100, description="每页条数（默认 20，最大 100）"),
    sort: str | None = Query(None, description="排序字段，前缀 - 表示降序（如 -created_at）"),
) -> PaginationParams:
    """分页查询参数依赖（HTTP 侧校验，service/仓储只接收中立对象）。"""
    return PaginationParams(page=page, limit=limit, sort=sort)


__all__ = [
    "get_current_user",
    "get_token_payload",
    "pagination_params",
    "require_llm_credential",
    "require_roles",
]
