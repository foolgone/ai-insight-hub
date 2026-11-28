"""租户只读查询（M4-A PR-2）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, User

CUSTOMER_KIND = "customer"


async def list_visible_tenants(session: AsyncSession, *, user: User) -> list[Tenant]:
    """普通用户只看自己租户；platform_admin 看 customer 租户；sentinel 永不返回。"""
    if user.role == "platform_admin":
        rows = await session.scalars(
            select(Tenant)
            .where(Tenant.kind == CUSTOMER_KIND, Tenant.status == "active")
            .order_by(Tenant.created_at.asc())
        )
        return list(rows.all())

    tenant = await session.get(Tenant, user.tenant_id)
    if tenant is None or tenant.kind != CUSTOMER_KIND:
        return []
    return [tenant]


__all__ = ["list_visible_tenants"]
