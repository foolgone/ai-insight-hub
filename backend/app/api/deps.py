"""API 依赖：当前用户、RBAC、归属校验（API 设计 §3.5）。

- ``get_token_payload``：解析 ``Authorization: Bearer <access>`` 并检查黑名单；
- ``get_current_user``：加载登录用户（不存在/软删 → USER_NOT_FOUND，停用 → AUTH_FORBIDDEN）；
- ``require_roles``：角色白名单（admin/user/viewer）；
- ``assert_owner``：资源归属校验（admin 全通，其余必须本人）。
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    LLMCredentialInvalidError,
    LLMCredentialNotConfiguredError,
    PermissionDeniedError,
    TokenExpiredError,
    UserNotFoundError,
)
from app.core.redis import is_token_blacklisted
from app.core.security import decode_token
from app.models import User
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
    payload: dict = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
) -> User:
    """当前登录用户。"""
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:  # pragma: no cover - 已由 decode_token 保证
        raise TokenExpiredError("Invalid token subject") from exc

    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise UserNotFoundError()
    if not user.is_active:
        raise PermissionDeniedError("User is inactive")
    return user


def require_roles(*roles: str) -> Callable:
    """生成角色校验依赖；角色不足 → 403 AUTH_FORBIDDEN。"""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("Insufficient role")
        return user

    return dependency


def assert_owner(resource_user_id: uuid.UUID | None, current_user: User) -> None:
    """校验资源归属：admin 全通，其余必须本人（越权 → 403）。"""
    if current_user.role == "admin":
        return
    if resource_user_id is None or resource_user_id != current_user.id:
        raise PermissionDeniedError("Access to another user's resource is forbidden")


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


__all__ = [
    "assert_owner",
    "get_current_user",
    "get_token_payload",
    "require_llm_credential",
    "require_roles",
]
