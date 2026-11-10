"""资源归属校验（分层中立，供 service 与 API 共用）。

放在 ``app.core`` 而不是 ``app.api``：归属判断是业务规则，不是 HTTP 关注点。
service 层若从 ``app.api`` 导入会形成「服务依赖 HTTP 层」的分层倒置。
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.core.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from app.models import User


def assert_owner(resource_user_id: uuid.UUID | None, current_user: User) -> None:
    """校验资源归属：admin 全通，其余必须本人（越权 → 403）。"""
    if current_user.role == "admin":
        return
    if resource_user_id is None or resource_user_id != current_user.id:
        raise PermissionDeniedError("Access to another user's resource is forbidden")


__all__ = ["assert_owner"]
