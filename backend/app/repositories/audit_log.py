"""audit_logs 仓储（M4-A PR-2）。"""
from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def add_cross_tenant_access(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    target_tenant_id: uuid.UUID,
    actor_tenant_id: uuid.UUID,
    method: str,
    path: str,
    ip_address: str | None,
    user_agent: str | None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        tenant_id=target_tenant_id,
        action="tenant.cross_access",
        resource_type="tenant",
        resource_id=target_tenant_id,
        details={
            "actor_tenant_id": str(actor_tenant_id),
            "target_tenant_id": str(target_tenant_id),
            "method": method,
            "path": path,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(row)
    await session.flush()
    return row


__all__: list[str] = ["add_cross_tenant_access"]
