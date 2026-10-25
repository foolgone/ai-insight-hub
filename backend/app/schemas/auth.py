"""认证相关 Schemas（API 设计 §2）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, ORMSchema


class RegisterRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str


class RefreshRequest(BaseSchema):
    refresh_token: str


class LogoutRequest(BaseSchema):
    refresh_token: str | None = None


class UserPublic(ORMSchema):
    id: uuid.UUID
    email: EmailStr
    name: str | None = None
    role: str
    created_at: datetime | None = None


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserPublic


class MessageResponse(BaseSchema):
    message: str


__all__ = [
    "LoginRequest",
    "LogoutRequest",
    "MessageResponse",
    "RefreshRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserPublic",
]
