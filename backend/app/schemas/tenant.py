"""租户只读 schema（M4-A PR-2）。"""
from __future__ import annotations

import uuid

from app.schemas.base import BaseSchema


class TenantItem(BaseSchema):
    id: uuid.UUID
    name: str
    slug: str
    status: str


__all__ = ["TenantItem"]
