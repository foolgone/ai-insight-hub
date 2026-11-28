"""租户只读接口（M4-A PR-2）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.tenant import TenantItem
from app.services import tenant_service

router = APIRouter()
READ_ROLES = ("platform_admin", "tenant_admin", "user", "viewer")


@router.get(
    "",
    response_model=list[TenantItem],
    response_model_by_alias=False,
    summary="可见租户列表（platform sentinel 永不返回）",
)
async def list_tenants(
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> list[TenantItem]:
    rows = await tenant_service.list_visible_tenants(session, user=user)
    return [TenantItem.model_validate(row, from_attributes=True) for row in rows]


__all__ = ["router"]
