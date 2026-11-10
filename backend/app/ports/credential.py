"""凭据端口：Agent 需要「拿到用户的 API Key」，但不需要知道它存在哪张表、怎么解密。

实现方：``app.services.credential_service.CredentialService``（Fernet 解密 + 审计）。
``session`` 类型用 ``Any``：端口不应把 SQLAlchemy 的会话类型泄漏进来。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ApiCredential:
    """解析后的明文凭据（只在内存中存活）。"""

    api_key: str
    status: str


@runtime_checkable
class CredentialPort(Protocol):
    """按用户取凭据 + 标记失效。"""

    async def resolve_api_key(self, session: Any, user_id: uuid.UUID) -> ApiCredential | None:
        """返回 ``None`` 表示用户未配置。"""
        ...

    async def mark_invalid(self, user_id: uuid.UUID) -> bool:
        """凭据被上游拒绝时标记失效（幂等）。"""
        ...


__all__ = ["ApiCredential", "CredentialPort"]
