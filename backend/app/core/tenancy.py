"""Tenant constants shared by models and migrations (M4-A tenant slice)."""

from __future__ import annotations

import uuid

# 固定默认租户 ID：迁移回填、模型 server_default、测试共用。
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_TENANT_ID_SQL = f"'{DEFAULT_TENANT_ID}'::uuid"
DEFAULT_TENANT_NAME = "默认租户"
DEFAULT_TENANT_SLUG = "default"

# 平台任务 sentinel 租户：只供 platform_admin 内部任务/CLI，不出现在租户列表。
PLATFORM_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
PLATFORM_TENANT_ID_SQL = f"'{PLATFORM_TENANT_ID}'::uuid"
PLATFORM_TENANT_NAME = "平台任务"
PLATFORM_TENANT_SLUG = "platform"

__all__ = [
    "DEFAULT_TENANT_ID",
    "DEFAULT_TENANT_ID_SQL",
    "DEFAULT_TENANT_NAME",
    "DEFAULT_TENANT_SLUG",
    "PLATFORM_TENANT_ID",
    "PLATFORM_TENANT_ID_SQL",
    "PLATFORM_TENANT_NAME",
    "PLATFORM_TENANT_SLUG",
]
