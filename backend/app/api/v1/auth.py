"""认证接口（API 设计 §2）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_token_payload
from app.core.database import get_db
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


def _token_response(user, tokens: auth_service.TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
        user=UserPublic.model_validate(user),
    )


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
    summary="登录",
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user, tokens = await auth_service.login(
        session, email=str(payload.email), password=payload.password
    )
    return _token_response(user, tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    response_model_by_alias=False,
    summary="刷新 Token（旧 refresh 立即失效）",
)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user, tokens = await auth_service.refresh(session, refresh_token=payload.refresh_token)
    return _token_response(user, tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    response_model_by_alias=False,
    summary="登出（access + refresh 加入黑名单）",
)
async def logout(
    payload: LogoutRequest,
    token_payload: dict = Depends(get_token_payload),
) -> MessageResponse:
    await auth_service.revoke_access_token(token_payload)
    if payload.refresh_token:
        await auth_service.revoke_refresh_token(payload.refresh_token)
    return MessageResponse(message="Logged out")


__all__ = ["router"]
