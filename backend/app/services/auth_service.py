"""认证服务（API 设计 §2）。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AIInsightHubException,
    AuthenticationError,
    PermissionDeniedError,
    RefreshTokenInvalidError,
    UserEmailExistsError,
)
from app.core.redis import blacklist_token, is_token_blacklisted
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_remaining_seconds,
    verify_password,
)
from app.models import User


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int


def _now_naive() -> datetime:
    """数据库 TIMESTAMP 无时区，统一存 UTC 朴素时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    name: str | None = None,
) -> User:
    """注册：邮箱唯一，密码 bcrypt 哈希，默认角色 user。"""
    if await get_user_by_email(session, email) is not None:
        raise UserEmailExistsError(details={"email": email})

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role="user",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def issue_tokens(user: User) -> TokenPair:
    access, _, _ = create_access_token(str(user.id), user.role)
    refresh, _, _ = create_refresh_token(str(user.id), user.role)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )


async def login(session: AsyncSession, *, email: str, password: str) -> tuple[User, TokenPair]:
    user = await get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise PermissionDeniedError("User is inactive")

    user.last_login_at = _now_naive()
    await session.flush()
    return user, await issue_tokens(user)


async def refresh(session: AsyncSession, *, refresh_token: str) -> tuple[User, TokenPair]:
    """刷新：校验 refresh → 旧 jti 立即失效（轮换）→ 签发新 token 对。"""
    payload = decode_token(refresh_token, "refresh")
    jti = str(payload["jti"])
    if await is_token_blacklisted(jti):
        raise RefreshTokenInvalidError("Refresh token already rotated or revoked")

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise RefreshTokenInvalidError("Invalid refresh token subject") from exc

    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise RefreshTokenInvalidError("User not available for refresh")

    await blacklist_token(jti, token_remaining_seconds(payload))
    return user, await issue_tokens(user)


async def revoke_access_token(payload: dict) -> None:
    await blacklist_token(str(payload["jti"]), token_remaining_seconds(payload))


async def revoke_refresh_token(refresh_token: str) -> None:
    """登出时尽量吊销 refresh；token 无效时不阻断登出（幂等）。"""
    try:
        payload = decode_token(refresh_token, "refresh")
    except AIInsightHubException:
        return
    await blacklist_token(str(payload["jti"]), token_remaining_seconds(payload))


__all__ = [
    "TokenPair",
    "get_user_by_email",
    "issue_tokens",
    "login",
    "refresh",
    "register",
    "revoke_access_token",
    "revoke_refresh_token",
]
