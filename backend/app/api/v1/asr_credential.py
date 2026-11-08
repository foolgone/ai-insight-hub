"""语音转写（ASR）配置路由（BYOK 扩展）。

三个端点（与 LLM 凭据对称）：
- ``PUT``    保存（**内部强制连通性校验**，失败不入库）；
- ``GET``    查询状态（不含明文/密文）；
- ``DELETE`` 删除（204，幂等）。

端点固定 ``/me``；``ASR_ENABLED=false`` 时 GET 返回 ``asr_enabled=false``，其余 404。
配置密文存 ``user_llm_credentials``（``provider='asr'``），不写 ``.env``。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core import credential_encryption as crypto
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AsrCredentialInvalidError
from app.core.url_guard import UnsafeUrlError, assert_safe_base_url
from app.models import User
from app.schemas.asr_credential import AsrCredentialIn, AsrCredentialStatus
from app.services.asr_service import (
    DEFAULT_ASR_LANGUAGE,
    SUPPORTED_LANGUAGES,
    AsrConfig,
    verify_config,
)
from app.services.credential_service import PROVIDER_ASR, credential_service

router = APIRouter()


def _ensure_enabled() -> None:
    if not settings.ASR_ENABLED:
        raise HTTPException(status_code=404, detail="ASR is not enabled")


def _validate_payload(payload: AsrCredentialIn) -> tuple[str, str, str | None]:
    """语义校验：返回 (规范化 base_url, model, language)；非法 → 400。"""
    try:
        base_url = assert_safe_base_url(payload.base_url)
    except UnsafeUrlError as exc:
        raise AsrCredentialInvalidError(f"服务地址不可用：{exc}") from exc

    api_key = (payload.api_key or "").strip()
    if len(api_key) < 8:
        raise AsrCredentialInvalidError("API Key 格式不符合要求（至少 8 位）")

    model = (payload.model or "").strip()
    if not model:
        raise AsrCredentialInvalidError("模型名不能为空（如 whisper-1 / FunAudioLLM/SenseVoiceSmall）")

    language = (payload.language or DEFAULT_ASR_LANGUAGE).strip() or None
    if language and language not in SUPPORTED_LANGUAGES:
        raise AsrCredentialInvalidError(f"不支持的语言：{language}")

    return base_url, model, language


@router.put(
    "/me/asr-credential",
    response_model=AsrCredentialStatus,
    response_model_by_alias=False,
    summary="保存（或覆盖）自己的语音转写配置；保存前强制连通性校验",
)
async def put_asr_credential(
    payload: AsrCredentialIn,
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> AsrCredentialStatus:
    _ensure_enabled()
    base_url, model, language = _validate_payload(payload)
    # 先确认加密密钥可用，避免白花一次校验请求
    crypto.ensure_encryption_ready()

    config = AsrConfig(
        base_url=base_url,
        api_key=payload.api_key.strip(),
        model=model,
        language=language,
    )
    ok, reason = await verify_config(config)
    if not ok:
        raise AsrCredentialInvalidError(reason or "语音转写配置连通性校验未通过")

    row = await credential_service.upsert(
        session,
        user_id=user.id,
        api_key=config.api_key,
        provider=PROVIDER_ASR,
        base_url=base_url,
        model=model,
        language=language,
    )
    return AsrCredentialStatus(
        asr_enabled=True,
        configured=True,
        base_url=row.base_url,
        model=row.model,
        language=row.language,
        key_hint=row.key_hint,
        status=row.status,
        verified_at=row.verified_at,
    )


@router.get(
    "/me/asr-credential",
    response_model=AsrCredentialStatus,
    response_model_by_alias=False,
    summary="查询自己的语音转写配置（不含明文/密文）",
)
async def get_asr_credential(
    user: User = Depends(require_roles("admin", "user", "viewer")),
    session: AsyncSession = Depends(get_db),
) -> AsrCredentialStatus:
    if not settings.ASR_ENABLED:
        return AsrCredentialStatus(asr_enabled=False, configured=False)
    status_dict = await credential_service.get_status(session, user.id, PROVIDER_ASR)
    return AsrCredentialStatus(asr_enabled=True, **status_dict)


@router.delete(
    "/me/asr-credential",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自己的语音转写配置（幂等）",
)
async def delete_asr_credential(
    user: User = Depends(require_roles("admin", "user")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    _ensure_enabled()
    await credential_service.delete(session, user.id, PROVIDER_ASR)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
