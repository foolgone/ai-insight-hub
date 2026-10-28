"""BYOK 凭据 Schemas（API 设计「BYOK 凭据」章节）。

- 入参只做**结构/格式**约束，语义校验（非空 ``base_url``、格式与连通性）统一在路由层
  转 400，避免 Pydantic 抛 ``ValueError`` 得到 422；
- 响应**永不含**明文/密文，只含 ``key_hint``。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, ORMSchema

# DeepSeek Key：sk- 前缀 + 至少 9 位（总长 >= 12，满足 key_hint 前 5 后 4 不重叠）
API_KEY_PATTERN = r"^sk-[A-Za-z0-9_-]{9,}$"


class CredentialIn(BaseSchema):
    """保存/校验凭据入参。

    只做类型与长度上限约束；**格式语义校验放在路由层**（非法 → 400
    ``LLM_CREDENTIAL_INVALID``），避免 Pydantic 抛 ``ValueError`` 被统一成 422。
    """

    api_key: str = Field(max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=100)


class CredentialStatus(ORMSchema):
    """凭据状态（PUT/GET 响应）。"""

    byok_enabled: bool = True
    configured: bool = False
    provider: str = "deepseek"
    key_hint: str | None = None
    status: str | None = None
    verified_at: datetime | None = None


__all__ = ["API_KEY_PATTERN", "CredentialIn", "CredentialStatus"]
