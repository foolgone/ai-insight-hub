"""认证接口（API 设计 §2）。

T4（2026-10-26）：refresh token 只通过 **HttpOnly Cookie** 下发/轮换/清除，
不再出现在响应体，前端无法用 JS 读取 → XSS 无法窃取长效凭证。

- Cookie：``HttpOnly`` + ``SameSite=Lax``（可配 strict/none）+ ``Path=/api/v1/auth``
  + ``Max-Age=JWT_REFRESH_TOKEN_EXPIRE_DAYS``；生产（HTTPS）需 ``AUTH_COOKIE_SECURE=true``；
- CSRF：``SameSite=Lax`` 使跨站 POST 不携带该 Cookie，MVP 以此作为缓解措施；
- 兼容：``/auth/refresh`` 仍接受请求体 ``refresh_token``（非浏览器客户端/旧测试），
  但浏览器路径只依赖 Cookie。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_token_payload
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AIInsightHubException, RefreshTokenInvalidError
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.services import auth_service

router = APIRouter()

_REFRESH_MAX_AGE = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


def _token_response(user, tokens: auth_service.TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
        user=UserPublic.model_validate(user),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=_REFRESH_MAX_AGE,
        path=settings.AUTH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def _extract_refresh_token(request: Request, payload: RefreshRequest | None) -> str:
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token and payload is not None:
        token = payload.refresh_token
    if not token:
        raise RefreshTokenInvalidError("Missing refresh token")
    return token


@router.post(
    "/register",
    status_code=201,
    response_model=UserPublic,
    response_model_by_alias=False,
    summary="注册",
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> UserPublic:
    user = await auth_service.register(
        session,
        email=str(payload.email),
        password=payload.password,
        name=payload.name,
    )
    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    response_model_by_alias=False,
    summary="登录（refresh token 写入 HttpOnly Cookie）",
)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user, tokens = await auth_service.login(
        session, email=str(payload.email), password=payload.password
    )
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_response(user, tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    response_model_by_alias=False,
    summary="刷新 Token（Cookie 轮换，旧 refresh 立即失效）",
)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    refresh_token = _extract_refresh_token(request, payload)
    try:
        user, tokens = await auth_service.refresh(session, refresh_token=refresh_token)
    except AIInsightHubException:
        _clear_refresh_cookie(response)
        raise
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_response(user, tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    response_model_by_alias=False,
    summary="登出（吊销 access + refresh，并清除 Cookie）",
)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    token_payload: dict = Depends(get_token_payload),
) -> MessageResponse:
    await auth_service.revoke_access_token(token_payload)
    refresh_token = request.cookies.get(settings.AUTH_COOKIE_NAME) or (
        payload.refresh_token if payload else None
    )
    if refresh_token:
        await auth_service.revoke_refresh_token(refresh_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out")


__all__ = ["router"]
