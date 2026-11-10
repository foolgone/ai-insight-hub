"""凭据服务（BYOK）：CRUD + 连通性校验 + 失效标记（需求 FR-BK-01~06 / 09 / 19）。

设计约束：
- 只操作当前登录用户（``user_id`` 由调用方从 JWT 取得，端点不接受他人 user_id）；
- 返回给外部的只有 ``key_hint``，明文只在进程内存中短暂存在；
- ``CREDENTIAL_ENCRYPTION_KEY`` 缺失 → ``LLMCredentialDecryptError``（fail closed）。

自迁移 013 起该表按 ``provider`` 区分用途：
- ``deepseek``：LLM Key（默认值，保持原调用方行为不变）；
- ``asr``：语音转写配置（base_url / model / language / api_key）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import credential_encryption as crypto
from app.core.database import SessionLocal
from app.core.exceptions import (
    AsrCredentialInvalidError,
    AsrCredentialNotConfiguredError,
    LLMCredentialDecryptError,
    LLMCredentialInvalidError,
    LLMCredentialNotConfiguredError,
)
from app.core.llm import LLMClient, LLMError
from app.ports.credential import ApiCredential
from app.models.llm_credential import UserLLMCredential
from app.models.security import AuditLog

__all__ = ["credential_service", "PROVIDER_LLM", "PROVIDER_ASR"]

PROVIDER_LLM = "deepseek"
PROVIDER_ASR = "asr"

# 审计 action（需求 §5 / FR-BK-18；最小写入，不含 Key 值）
AUDIT_CREDENTIAL_CONFIGURED = "credential_configured"
AUDIT_CREDENTIAL_DELETED = "credential_deleted"
AUDIT_CREDENTIAL_INVALID = "credential_invalid"


def _utc_now_naive() -> datetime:
    """库内 DateTime 列无时区，写入前统一转 naive（asyncpg 不接受 aware）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _resource_type(provider: str) -> str:
    return "asr_credential" if provider == PROVIDER_ASR else "llm_credential"


def _write_audit(session, user_id: uuid.UUID, action: str, provider: str) -> None:
    """写一条最小审计（不含任何 Key 信息）；resource_id 为 UUID 列。"""
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=_resource_type(provider),
            resource_id=user_id,
            details={"provider": provider},
        )
    )


class CredentialService:
    """用户凭据读写（LLM / ASR 共用）。"""

    async def get_credential(
        self, session: AsyncSession, user_id: uuid.UUID, provider: str = PROVIDER_LLM
    ) -> UserLLMCredential | None:
        """按 (user_id, provider) 取凭据行（不解密）。"""
        return await session.scalar(
            select(UserLLMCredential).where(
                UserLLMCredential.user_id == user_id,
                UserLLMCredential.provider == provider,
            )
        )

    async def resolve_api_key(
        self, session: AsyncSession, user_id: uuid.UUID, provider: str = PROVIDER_LLM
    ) -> ApiCredential | None:
        """凭据端口的实现：返回解密后的明文 Key（未配置 → ``None``）。

        Agent 通过 ``CredentialPort`` 调用，不需要知道表结构、加密方式与审计。
        """
        row = await self.get_credential(session, user_id, provider)
        if row is None:
            return None
        return ApiCredential(api_key=self.decrypt_credential(row), status=row.status)

    async def get_status(
        self, session: AsyncSession, user_id: uuid.UUID, provider: str = PROVIDER_LLM
    ) -> dict:
        """凭据状态（不含明文/密文）。``base_url``/``model``/``language`` 非敏感，可回显。"""
        row = await self.get_credential(session, user_id, provider)
        if row is None:
            return {"configured": False}
        return {
            "configured": True,
            "provider": row.provider,
            "key_hint": row.key_hint,
            "base_url": row.base_url,
            "model": row.model,
            "language": row.language,
            "status": row.status,
            "verified_at": row.verified_at,
        }

    async def verify(self, api_key: str) -> bool:
        """连通性校验：真心调一次 LLM（max_tokens=1）。

        401/402(欠费)/429/5xx/连接失败均视为"不可用"——需求 §15「用户 Key 质量差/欠费」
        与 D4 都要求失败即不保存。
        """
        try:
            async with LLMClient(api_key=api_key) as client:
                await client.chat(messages=[{"role": "user", "content": "hi"}], max_tokens=1)
            return True
        except LLMError as exc:
            logger.info("llm credential verify failed type={}", type(exc).__name__)
            return False

    async def upsert(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        api_key: str,
        provider: str = PROVIDER_LLM,
        base_url: str | None = None,
        model: str | None = None,
        language: str | None = None,
    ) -> UserLLMCredential:
        """新增或覆盖凭据（一人一 provider 一条）；调用方须已通过 verify。"""
        ciphertext = crypto.encrypt(api_key)
        hint = crypto.make_hint(api_key)
        row = await self.get_credential(session, user_id, provider)
        if row is None:
            row = UserLLMCredential(
                user_id=user_id,
                provider=provider,
                base_url=base_url,
                model=model,
                language=language,
                encrypted_api_key=ciphertext,
                key_hint=hint,
                status="active",
                verified_at=_utc_now_naive(),
            )
            session.add(row)
        else:
            row.base_url = base_url
            row.model = model
            row.language = language
            row.encrypted_api_key = ciphertext
            row.key_hint = hint
            row.status = "active"
            row.verified_at = _utc_now_naive()
            row.updated_at = _utc_now_naive()
        _write_audit(session, user_id, AUDIT_CREDENTIAL_CONFIGURED, provider)
        await session.flush()
        return row

    async def delete(
        self, session: AsyncSession, user_id: uuid.UUID, provider: str = PROVIDER_LLM
    ) -> bool:
        """删除凭据；返回是否真的删掉了（幂等）。"""
        result = await session.execute(
            delete(UserLLMCredential).where(
                UserLLMCredential.user_id == user_id,
                UserLLMCredential.provider == provider,
            )
        )
        if result.rowcount:
            _write_audit(session, user_id, AUDIT_CREDENTIAL_DELETED, provider)
        await session.flush()
        return bool(result.rowcount)

    def decrypt_credential(self, row: UserLLMCredential) -> str:
        """解密凭据；密钥更换/缺失 → ``LLMCredentialDecryptError``（500）。"""
        try:
            return crypto.decrypt(row.encrypted_api_key)
        except LLMCredentialDecryptError:
            logger.error(
                "credential decrypt failed user_id={} provider={}", row.user_id, row.provider
            )
            raise

    async def mark_invalid(self, user_id: uuid.UUID, provider: str = PROVIDER_LLM) -> bool:
        """幂等标记失效（``WHERE status != 'invalid'``），返回是否本次真正更新。

        用**独立会话**提交，避免被 worker 任务事务回滚吞掉。
        """
        try:
            async with SessionLocal() as session:
                result = await session.execute(
                    update(UserLLMCredential)
                    .where(
                        UserLLMCredential.user_id == user_id,
                        UserLLMCredential.provider == provider,
                        UserLLMCredential.status != "invalid",
                    )
                    .values(status="invalid", updated_at=_utc_now_naive())
                )
                if result.rowcount:
                    _write_audit(session, user_id, AUDIT_CREDENTIAL_INVALID, provider)
                await session.commit()
                return bool(result.rowcount)
        except Exception:  # noqa: BLE001 - 标记失败不能掩盖原始 401
            logger.exception(
                "credential mark_invalid failed user_id={} provider={}", user_id, provider
            )
            return False

    async def require_active_key(
        self, session: AsyncSession, user_id: uuid.UUID, provider: str = PROVIDER_LLM
    ) -> str:
        """取用户明文 Key；无凭据 → 428，已失效 → 400。"""
        row = await self.get_credential(session, user_id, provider)
        if row is None:
            if provider == PROVIDER_ASR:
                raise AsrCredentialNotConfiguredError()
            raise LLMCredentialNotConfiguredError()
        if row.status != "active":
            if provider == PROVIDER_ASR:
                raise AsrCredentialInvalidError()
            raise LLMCredentialInvalidError()
        return self.decrypt_credential(row)


credential_service = CredentialService()
