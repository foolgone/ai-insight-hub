"""B-209 RBAC/归属校验单测（不连库）。"""
from __future__ import annotations

import uuid

import pytest

from app.api.deps import assert_owner
from app.core.exceptions import PermissionDeniedError
from tests.factories import UserFactory

pytestmark = pytest.mark.unit


def _user(role: str) -> object:
    return UserFactory(role=role, id=uuid.uuid4())


def test_admin_can_access_any_resource() -> None:
    admin = _user("admin")
    assert_owner(uuid.uuid4(), admin)


def test_user_can_access_own_resource() -> None:
    user = _user("user")
    assert_owner(user.id, user)


def test_user_cannot_access_other_resource() -> None:
    user = _user("user")
    with pytest.raises(PermissionDeniedError):
        assert_owner(uuid.uuid4(), user)


def test_viewer_cannot_access_other_resource() -> None:
    viewer = _user("viewer")
    with pytest.raises(PermissionDeniedError):
        assert_owner(uuid.uuid4(), viewer)


def test_none_owner_is_denied_for_non_admin() -> None:
    user = _user("user")
    with pytest.raises(PermissionDeniedError):
        assert_owner(None, user)
