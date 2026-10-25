"""用户接口（API 设计 §4）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.auth import MessageResponse
from app.schemas.user import PasswordChangeRequest, UserMe, UserUpdateRequest
from app.services import user_service

router = APIRouter()


@router.get(
    "/me",
    response_model=UserMe,
    response_model_by_alias=False,
    summary="获取当前用户信息",
)
async def get_me(
    user: User = Depends(require_roles("admin", "user", "viewer")),
) -> UserMe:
    return UserMe.model_validate(user)


@router.patch(
    "/me",
    response_model=UserMe,
    response_model_by_alias=False,
    summary="更新当前用户信息（局部更新）",
)
async def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> UserMe:
    data = payload.model_dump(exclude_unset=True)
    updated = await user_service.update_profile(session, user, data)
    return UserMe.model_validate(updated)


@router.post(
    "/me/password",
    response_model=MessageResponse,
    response_model_by_alias=False,
    summary="修改密码",
)
async def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await user_service.change_password(
        session,
        user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Password updated")


__all__ = ["router"]
