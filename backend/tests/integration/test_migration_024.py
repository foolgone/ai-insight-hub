"""024 M4-A PR-2：platform sentinel、四角色与 admin 映射。"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.tenancy import (
    DEFAULT_TENANT_ID,
    DEFAULT_TENANT_SLUG,
    PLATFORM_TENANT_ID,
    PLATFORM_TENANT_SLUG,
)

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
REV_023 = "a7c4e9f2b6d1"


def _sync_url() -> str:
    return settings.DATABASE_URL.replace("+asyncpg", "")


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _fetch(sql: str, **params: object) -> list[tuple[object, ...]]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(conn.execute(text(sql), params).all())
    finally:
        engine.dispose()


def _scalar(sql: str, **params: object):
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), params).scalar()
    finally:
        engine.dispose()


def test_024_platform_sentinel_and_role_constraint() -> None:
    rows = _fetch(
        "SELECT id, slug, kind, status FROM tenants WHERE id IN (:default, :platform)",
        default=DEFAULT_TENANT_ID,
        platform=PLATFORM_TENANT_ID,
    )
    by_slug = {row[1]: row for row in rows}
    assert by_slug[DEFAULT_TENANT_SLUG][2] == "customer"
    assert by_slug[PLATFORM_TENANT_SLUG][2] == "platform"
    assert by_slug[PLATFORM_TENANT_SLUG][3] == "active"

    kind_nullable = _scalar(
        """
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name='tenants' AND column_name='kind'
        """
    )
    assert kind_nullable == "NO"
    index_exists = _scalar("SELECT 1 FROM pg_indexes WHERE indexname='idx_tenants_kind_status'")
    assert index_exists == 1

    role_check = _scalar(
        """
        SELECT pg_get_constraintdef(oid) FROM pg_constraint
        WHERE conrelid='users'::regclass AND conname='ck_users_role_valid'
        """
    )
    for role in ("platform_admin", "tenant_admin", "user", "viewer"):
        assert role in role_check
    assert "'admin'" not in role_check


def test_024_platform_tenant_hidden_from_customer_scope() -> None:
    # 租户列表/切换器未来统一使用 kind='customer' 过滤。
    visible = [
        row[0]
        for row in _fetch("SELECT slug FROM tenants WHERE kind='customer' AND status='active'")
    ]
    assert DEFAULT_TENANT_SLUG in visible
    assert PLATFORM_TENANT_SLUG not in visible

    # 普通用户不得加入 platform sentinel。
    assert (
        _scalar(
            "SELECT count(*) FROM users WHERE tenant_id = :id",
            id=PLATFORM_TENANT_ID,
        )
        == 0
    )


def test_024_maps_admin_to_tenant_admin() -> None:
    config = _alembic_config()
    command.downgrade(config, REV_023)
    user_id = uuid.uuid4()
    try:
        engine = create_engine(_sync_url())
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, password_hash, role) "
                        "VALUES (:id, :email, 'x', 'admin')"
                    ),
                    {"id": user_id, "email": f"role024-{uuid.uuid4().hex[:8]}@example.com"},
                )
        finally:
            engine.dispose()
        command.upgrade(config, "head")
        role = _scalar("SELECT role FROM users WHERE id = :id", id=user_id)
        assert role == "tenant_admin"
    finally:
        engine = create_engine(_sync_url())
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        finally:
            engine.dispose()
        command.upgrade(config, "head")


def test_024_upgrade_downgrade_twice() -> None:
    config = _alembic_config()
    for _ in range(2):
        command.downgrade(config, REV_023)
        assert (
            _scalar(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='tenants' AND column_name='kind'"
            )
            == 0
        )
        assert (
            _scalar(
                "SELECT count(*) FROM tenants WHERE id = :id",
                id=PLATFORM_TENANT_ID,
            )
            == 0
        )
        command.upgrade(config, "head")
        assert (
            _scalar("SELECT kind FROM tenants WHERE id = :id", id=PLATFORM_TENANT_ID) == "platform"
        )
        assert (
            _scalar(
                "SELECT count(*) FROM tenants WHERE id = :default AND kind='customer'",
                default=DEFAULT_TENANT_ID,
            )
            == 1
        )
