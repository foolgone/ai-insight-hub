"""BYOK 凭据路由（需求 §7；API 设计「BYOK 凭据」章节）。

四个端点：
- ``PUT``    保存（**内部强制连通性校验**，失败不入库 —— D4 的"验证并保存"单一操作）；
- ``GET``    查询状态（只回 ``key_hint``，永不回明文/密文）；
- ``DELETE`` 删除（204；删除后 AI 操作恢复 428）；
- ``POST .../verify`` 独立连通性测试（保留实现、限流，本期前端不调用；见拍板 P-2）。

端点固定 ``/me``，不接受他人 user_id，admin 也只能读写自己（FR-BK-17）。
``BYOK_ENABLED=false`` 时：GET 返回 ``byok_enabled=false``，其余端点 404（开关矩阵见开发指南 §2.3）。
"""
from __future__ import annotations

import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core import credential_encryption as crypto
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import LLMCredentialInvalidError, RateLimitExceededError
from app.core.redis import get_redis
from app.models import User
from app.schemas.llm_credential import API_KEY_PATTERN, CredentialIn, CredentialStatus
from app.services.credential_service import credential_service

router = APIRouter()

_KEY_RE = re.compile(API_KEY_PATTERN)


def _ensure_enabled() -> None:
    if not settings.BYOK_ENABLED:
        raise HTTPException(status_code=404, detail="BYOK is not enabled")


def _validate_payload(payload: CredentialIn) -> None:
    """Phase 1 语义校验：一律 400 ``LLM_CREDENTIAL_INVALID``（不走 Pydantic，避免 422）。"""
    if payload.base_url and payload.base_url.strip():
        raise LLMCredentialInvalidError("当前版本仅支持 DeepSeek 官方端点，不支持自定义 base_url")
    if len(payload.api_key) < 12 or not _KEY_RE.match(payload.api_key):
        raise LLMCredentialInvalidError("api_key 格式不符合要求（需 sk- 开头且长度足够）")


async def _enforce_verify_rate_limit(user_id: uuid.UUID) -> None:
    """verify 限流：固定窗口 ≤ ``LLM_CREDENTIAL_VERIFY_PER_MINUTE`` 次/分钟/用户。"""
    window = int(time.time() // 60)
    key = f"byok:verify:{user_id}:{window}"
    redis = get_redis()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > settings.LLM_CREDENTIAL_VERIFY_PER_MINUTE:
        reset_at = (window + 1) * 60
        raise RateLimitExceededError(
            "Too many verify requests",
            headers={"Retry-After": str(max(1, reset_at - int(time.time())))},
        )


@router.put(
    "/me/llm-credential",
    response_model=CredentialStatus,
    response_model_by_alias=False,
    summary="保存（或覆盖）自己的 LLM API Key；保存前强制连通性校验",
)
async def put_llm_credential(
    payload: CredentialIn,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> CredentialStatus:
    _ensure_enabled()
    _validate_payload(payload)
    # 先确认加密密钥可用，避免白花一次 verify 的调用成本
    crypto.ensure_encryption_ready()

    if not await credential_service.verify(payload.api_key):
        raise LLMCredentialInvalidError("API Key 连通性校验未通过，请检查 Key 是否正确或余额是否充足")

    row = await credential_service.upsert(session, user_id=user.id, api_key=payload.api_key)
    return CredentialStatus(
        byok_enabled=True,
        configured=True,
        provider=row.provider,
        key_hint=row.key_hint,
        status=row.status,
        verified_at=row.verified_at,
    )


@router.get(
    "/me/llm-credential",
    response_model=CredentialStatus,
    response_model_by_alias=False,
    summary="查询自己的凭据状态（不含明文/密文）",
)
async def get_llm_credential(
    user: User = Depends(require_roles("admin", "user", "viewer")),
    session: AsyncSession = Depends(get_db),
) -> CredentialStatus:
    if not settings.BYOK_ENABLED:
        return CredentialStatus(byok_enabled=False, configured=False)
    status_dict = await credential_service.get_status(session, user.id)
    return CredentialStatus(byok_enabled=True, **status_dict)


@router.delete(
    "/me/llm-credential",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自己的 LLM API Key（幂等）",
)
async def delete_llm_credential(
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    _ensure_enabled()
    await credential_service.delete(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/llm-credential/verify",
    response_model=CredentialStatus,
    response_model_by_alias=False,
    summary="连通性测试（限流；本期前端不调用，供后续重新验证）",
)
async def verify_llm_credential(
    payload: CredentialIn,
    user: User = Depends(require_roles("admin", "user")),
) -> CredentialStatus:
    _ensure_enabled()
    _validate_payload(payload)
    await _enforce_verify_rate_limit(user.id)
    if not await credential_service.verify(payload.api_key):
        raise LLMCredentialInvalidError("API Key 无效或账户无余额")
    return CredentialStatus(byok_enabled=True, configured=False)


__all__ = ["router"]
