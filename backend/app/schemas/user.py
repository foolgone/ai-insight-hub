"""用户相关 Schemas（API 设计 §4）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, ORMSchema


class UserMe(ORMSchema):
    id: uuid.UUID
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    quota: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class UserUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)


class PasswordChangeRequest(BaseSchema):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


__all__ = ["PasswordChangeRequest", "UserMe", "UserUpdateRequest"]
