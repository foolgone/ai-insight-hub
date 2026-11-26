"""Tenant constants shared by models and migrations (M4-A tenant slice)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.exceptions import TenantContextMissingError

# 固定默认租户 ID：迁移回填与测试共用。
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_TENANT_NAME = "默认租户"
DEFAULT_TENANT_SLUG = "default"

# 平台任务 sentinel 租户：只供 platform_admin 内部任务/CLI，不出现在租户列表。
PLATFORM_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
PLATFORM_TENANT_ID_SQL = f"'{PLATFORM_TENANT_ID}'::uuid"
PLATFORM_TENANT_NAME = "平台任务"
PLATFORM_TENANT_SLUG = "platform"


@dataclass(frozen=True)
class TenantContext:
    """一次请求/任务使用的租户上下文。"""

    tenant_id: uuid.UUID
    enforced: bool
    is_platform_admin: bool
    actor_user_id: uuid.UUID | None = None
    requested_tenant_id: uuid.UUID | None = None


def attach_tenant_context(user: Any, context: TenantContext) -> None:
    setattr(user, "_tenant_context", context)


def context_for_user(user: Any) -> TenantContext:
    context = getattr(user, "_tenant_context", None)
    if context is not None:
        return context
    if settings.TENANT_ENFORCEMENT_ENABLED:
        # 强制模式：调用方必须显式 attach（API 由 deps 完成；Celery/CLI 用 system_context）。
        raise TenantContextMissingError(details={"user_id": str(getattr(user, "id", ""))})
    # flag=false：保留单租户行为，但写入仍使用用户租户。
    return TenantContext(
        tenant_id=user.tenant_id,
        enforced=False,
        is_platform_admin=user.role == "platform_admin",
        actor_user_id=user.id,
    )


def tenant_scope(user: Any) -> uuid.UUID | None:
    """强制模式下返回 tenant_id；flag=false 返回 None（保持旧行为）。"""
    context = context_for_user(user)
    return context.tenant_id if context.enforced else None


def system_context(
    tenant_id: uuid.UUID, *, actor_user_id: uuid.UUID | None = None
) -> TenantContext:
    """内部任务/CLI 的显式租户上下文（租户来自已持久化父资源，不来自请求头）。"""
    return TenantContext(
        tenant_id=tenant_id,
        enforced=True,
        is_platform_admin=False,
        actor_user_id=actor_user_id,
    )


def tenant_id_for_write(user: Any) -> uuid.UUID:
    return context_for_user(user).tenant_id


def require_tenant(resource: Any, user: Any, error_cls: Any) -> None:
    """flag=true 时跨租户资源统一 404（由调用方传领域 NotFound 异常）。"""
    scope = tenant_scope(user)
    if scope is None:
        return
    if getattr(resource, "tenant_id", None) != scope:
        raise error_cls(details={"resource_id": str(getattr(resource, "id", ""))})


def apply_tenant_filter(stmt: Any, model: Any, user: Any) -> Any:
    scope = tenant_scope(user)
    if scope is not None:
        stmt = stmt.where(model.tenant_id == scope)
    return stmt


__all__ = [
    "DEFAULT_TENANT_ID",
    "DEFAULT_TENANT_NAME",
    "DEFAULT_TENANT_SLUG",
    "PLATFORM_TENANT_ID",
    "PLATFORM_TENANT_ID_SQL",
    "PLATFORM_TENANT_NAME",
    "PLATFORM_TENANT_SLUG",
    "TenantContext",
    "apply_tenant_filter",
    "attach_tenant_context",
    "context_for_user",
    "require_tenant",
    "system_context",
    "tenant_id_for_write",
    "tenant_scope",
]
