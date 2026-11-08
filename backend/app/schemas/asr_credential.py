"""ASR 转写配置 Schemas（BYOK 扩展，对应「语音转写设置」）。

与 LLM 凭据一致：
- 入参只做**长度**约束，语义校验（地址安全、格式、连通性）统一在路由层转 400，
  避免 Pydantic 抛 ``ValueError`` 得到 422；
- 响应**永不含**明文/密文，只含 ``key_hint`` 与用户自己填写的非敏感配置。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, ORMSchema


class AsrCredentialIn(BaseSchema):
    """保存 ASR 配置入参。"""

    base_url: str = Field(default="", max_length=500)
    api_key: str = Field(default="", max_length=200)
    model: str = Field(default="", max_length=100)
    language: str | None = Field(default=None, max_length=10)


class AsrCredentialStatus(ORMSchema):
    """ASR 配置状态（PUT/GET 响应）。"""

    asr_enabled: bool = True
    configured: bool = False
    base_url: str | None = None
    model: str | None = None
    language: str | None = None
    key_hint: str | None = None
    status: str | None = None
    verified_at: datetime | None = None


__all__ = ["AsrCredentialIn", "AsrCredentialStatus"]
