"""JWT 与密码哈希（API 设计 §2，开发规范 §2.3）。

Token 约定（API §2.2~§2.5）：
- access：60 分钟（``JWT_ACCESS_TOKEN_EXPIRE_MINUTES``），业务接口唯一凭据；
- refresh：7 天（``JWT_REFRESH_TOKEN_EXPIRE_DAYS``），只能用于 ``/auth/refresh``，刷新即轮换；
- claims：``sub`` / ``role`` / ``type`` / ``jti`` / ``iat`` / ``exp``。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import RefreshTokenInvalidError, TokenExpiredError

TokenType = Literal["access", "refresh"]

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """bcrypt 哈希（不存明文；数据库设计 §3.1）。"""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验密码；哈希非法时返回 False 而不是抛错。"""
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(user_id: str, role: str, token_type: TokenType) -> tuple[str, str, datetime]:
    """生成 Token，返回 ``(token, jti, expires_at)``。"""
    now = _now()
    if token_type == "access":
        expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expires_at = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def create_access_token(user_id: str, role: str) -> tuple[str, str, datetime]:
    return create_token(user_id, role, "access")


def create_refresh_token(user_id: str, role: str) -> tuple[str, str, datetime]:
    return create_token(user_id, role, "refresh")


def _invalid_error(token_type: TokenType, message: str) -> Exception:
    if token_type == "access":
        return TokenExpiredError(message)
    return RefreshTokenInvalidError(message)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """解码并校验 Token；失败时抛领域异常（按类型映射错误码）。"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise _invalid_error(expected_type, "Token expired") from exc
    except JWTError as exc:
        raise _invalid_error(expected_type, "Invalid token") from exc

    if payload.get("type") != expected_type:
        raise _invalid_error(expected_type, "Invalid token type")
    if not payload.get("sub") or not payload.get("jti"):
        raise _invalid_error(expected_type, "Invalid token payload")
    return payload


def token_remaining_seconds(payload: dict[str, Any]) -> int:
    """Token 剩余有效期（用于黑名单 TTL）。"""
    exp = payload.get("exp")
    if exp is None:
        return 0
    return max(0, int(float(exp) - _now().timestamp()))


__all__ = [
    "TokenType",
    "create_access_token",
    "create_refresh_token",
    "create_token",
    "decode_token",
    "hash_password",
    "token_remaining_seconds",
    "verify_password",
]
