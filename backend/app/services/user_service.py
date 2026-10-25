"""用户服务（API 设计 §4）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import FrameworkErrorCode
from app.core.exceptions import AIInsightHubException
from app.core.security import hash_password, verify_password
from app.models import User


async def update_profile(session: AsyncSession, user: User, data: dict[str, Any]) -> User:
    """局部更新 profile（只更新显式传入的字段）。"""
    for field in ("name", "avatar_url"):
        if field in data:
            setattr(user, field, data[field])
    await session.flush()
    await session.refresh(user)
    return user


async def change_password(
    session: AsyncSession,
    user: User,
    *,
    current_password: str,
    new_password: str,
) -> None:
    """修改密码：原密码错误返回 400（API §4.3）。"""
    if not verify_password(current_password, user.password_hash):
        raise AIInsightHubException(
            "Current password is incorrect",
            code=FrameworkErrorCode.BAD_REQUEST,
            status_code=400,
        )
    user.password_hash = hash_password(new_password)
    await session.flush()


__all__ = ["change_password", "update_profile"]
