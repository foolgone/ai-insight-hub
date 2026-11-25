"""PR-2 租户隔离：JWT tenant claim、TenantContext、404 与审计。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.core.tenancy import DEFAULT_TENANT_ID, PLATFORM_TENANT_ID
from app.models import (
    AuditLog,
    QaDataset,
    QaDatasetItem,
    QaDatasetVersion,
    RagEvaluationRun,
    RagTrace,
    Report,
    Task,
    Tenant,
)
from tests.factories import UserFactory, persist

pytestmark = pytest.mark.integration

BASE = "/api/v1"
PASSWORD = "tenant12345"


async def _login(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = await client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _tenant(db_session, slug: str, *, kind: str = "customer") -> Tenant:
    tenant = Tenant(id=uuid.uuid4(), name=f"tenant-{slug}", slug=slug, kind=kind)
    await persist(db_session, tenant)
    return tenant


async def _user(db_session, tenant: Tenant, *, role: str = "user"):
    user = UserFactory(password_hash=hash_password(PASSWORD), role=role)
    user.tenant_id = tenant.id
    await persist(db_session, user)
    return user


async def _headers(client, db_session, tenant: Tenant, *, role: str = "user"):
    user = await _user(db_session, tenant, role=role)
    return user, await _login(client, user.email)


async def _datasource(client, headers, name: str) -> str:
    response = await client.post(
        f"{BASE}/datasources",
        headers=headers,
        json={"name": name, "type": "customer_service"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _dataset(client, db_session, tenant: Tenant, user, name: str):
    dataset = QaDataset(tenant_id=tenant.id, user_id=user.id, name=name, source_type="doc")
    await persist(db_session, dataset)
    version = QaDatasetVersion(
        tenant_id=tenant.id,
        dataset_id=dataset.id,
        version=1,
        status="published",
        item_count=1,
        checksum=uuid.uuid4().hex,
    )
    await persist(db_session, version)
    item = QaDatasetItem(
        tenant_id=tenant.id,
        version_id=version.id,
        item_key="Q1",
        query="退款多久到账？",
    )
    await persist(db_session, item)
    return dataset, version, item


async def test_jwt_tenant_claim_and_legacy_compatibility(client, db_session) -> None:
    tenant = await _tenant(db_session, f"jwt-{uuid.uuid4().hex[:6]}")
    user, headers = await _headers(client, db_session, tenant)

    me = await client.get(f"{BASE}/users/me", headers=headers)
    assert me.status_code == 200, me.text

    # 旧 token（无 tenant claim）在 grace 期内按 DB 租户解析。
    old_token, _, _ = create_access_token(str(user.id), user.role)
    old_headers = {"Authorization": f"Bearer {old_token}"}
    assert (await client.get(f"{BASE}/users/me", headers=old_headers)).status_code == 200

    # claim 与 DB 不一致 → 401
    mismatch, _, _ = create_access_token(str(user.id), user.role, tenant_id=str(uuid.uuid4()))
    response = await client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {mismatch}"})
    assert response.status_code == 401

    # 超过 grace 的旧 token → 401
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now - timedelta(days=settings.TENANT_CLAIM_GRACE_DAYS + 1),
        "exp": now + timedelta(minutes=5),
    }
    expired = jose_jwt.encode(
        expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    response = await client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401

    # 旧 refresh（无 tenant claim）刷新后签发带 tenant 的新 access。
    old_refresh, _, _ = create_refresh_token(str(user.id), user.role)
    refreshed = await client.post(f"{BASE}/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200, refreshed.text
    new_payload = decode_token(refreshed.json()["access_token"], "access")
    assert new_payload["tenant_id"] == str(user.tenant_id)


async def test_flag_false_preserves_single_tenant_behavior(client, db_session) -> None:
    tenant_a = await _tenant(db_session, f"a-{uuid.uuid4().hex[:6]}")
    tenant_b = await _tenant(db_session, f"b-{uuid.uuid4().hex[:6]}")
    user_a, headers_a = await _headers(client, db_session, tenant_a)
    user_b, headers_b = await _headers(client, db_session, tenant_b)
    ds_a = await _datasource(client, headers_a, "tenant-a-ds")
    ds_b = await _datasource(client, headers_b, "tenant-b-ds")

    listed = await client.get(f"{BASE}/datasources", headers=headers_a)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert ds_a in ids
    assert ds_b not in ids

    # flag=false：仍按 user 归属，跨用户返回 403（不是租户 404）。
    response = await client.get(f"{BASE}/datasources/{ds_b}", headers=headers_a)
    assert response.status_code == 403


async def test_flag_true_cross_tenant_returns_404(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TENANT_ENFORCEMENT_ENABLED", True)
    tenant_a = await _tenant(db_session, f"a-{uuid.uuid4().hex[:6]}")
    tenant_b = await _tenant(db_session, f"b-{uuid.uuid4().hex[:6]}")
    user_a, headers_a = await _headers(client, db_session, tenant_a)
    user_b, headers_b = await _headers(client, db_session, tenant_b)
    ds_a = await _datasource(client, headers_a, "tenant-a-ds")
    ds_b = await _datasource(client, headers_b, "tenant-b-ds")

    listed = await client.get(f"{BASE}/datasources", headers=headers_a)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert ds_a in ids
    assert ds_b not in ids

    for method, path in (
        ("get", f"{BASE}/datasources/{ds_b}"),
        ("patch", f"{BASE}/datasources/{ds_b}"),
        ("delete", f"{BASE}/datasources/{ds_b}"),
    ):
        response = await getattr(client, method)(
            path, headers=headers_a, **({"json": {"name": "x"}} if method == "patch" else {})
        )
        assert response.status_code == 404, (method, path, response.text)

    dataset_b, version_b, item_b = await _dataset(
        client, db_session, tenant_b, user_b, "tenant-b-dataset"
    )
    for path in (
        f"{BASE}/qa-datasets/{dataset_b.id}",
        f"{BASE}/qa-datasets/{dataset_b.id}/versions",
        f"{BASE}/qa-datasets/{dataset_b.id}/versions/{version_b.id}/items",
    ):
        response = await client.get(path, headers=headers_a)
        assert response.status_code == 404, (path, response.text)

    report_create = await client.post(
        f"{BASE}/datasources/{ds_b}/reports",
        headers=headers_a,
        json={
            "title": "cross-tenant-report",
            "report_type": "quality",
            "format": "markdown",
        },
    )
    assert report_create.status_code == 404, report_create.text

    task_b = Task(
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        task_type="clean",
        status="pending",
    )
    await persist(db_session, task_b)
    assert (await client.get(f"{BASE}/tasks/{task_b.id}", headers=headers_a)).status_code == 404
    listed_tasks = await client.get(f"{BASE}/tasks", headers=headers_a)
    assert listed_tasks.status_code == 200
    assert str(task_b.id) not in {item["id"] for item in listed_tasks.json()["items"]}

    for path in (
        f"{BASE}/datasources/{ds_b}/reports",
        f"{BASE}/datasources/{ds_b}/analysis/quality",
        f"{BASE}/datasources/{ds_b}/knowledge/faq",
    ):
        response = await client.get(path, headers=headers_a)
        assert response.status_code == 404, (path, response.text)

    report_b = Report(
        tenant_id=tenant_b.id,
        datasource_id=uuid.UUID(ds_b),
        user_id=user_b.id,
        title="tenant-b-report",
        report_type="quality",
        format="markdown",
        status="completed",
        file_path="reports/missing.md",
    )
    await persist(db_session, report_b)
    assert (await client.get(f"{BASE}/reports/{report_b.id}", headers=headers_a)).status_code == 404
    assert (
        await client.get(f"{BASE}/reports/{report_b.id}/download", headers=headers_a)
    ).status_code == 404

    trace_b = RagTrace(
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        adapter="mock",
        mode="query",
        query="q",
        status="success",
    )
    await persist(db_session, trace_b)
    assert (
        await client.get(f"{BASE}/rag/traces/{trace_b.id}", headers=headers_a)
    ).status_code == 404

    run_b = RagEvaluationRun(
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        dataset_id=dataset_b.id,
        dataset_name=dataset_b.name,
        dataset_version_id=version_b.id,
        execution_mode="query",
        adapter="mock",
        retrieval_config={},
        judge_config={},
        config_snapshot={},
        item_selection={},
        status="completed",
        total_items=1,
    )
    await persist(db_session, run_b)
    for path in (
        f"{BASE}/rag/evaluations/{run_b.id}",
        f"{BASE}/rag/evaluations/{run_b.id}/results",
        f"{BASE}/rag/evaluations/{run_b.id}/failures",
    ):
        response = await client.get(path, headers=headers_a)
        assert response.status_code == 404, (path, response.text)


async def test_platform_admin_header_switch_and_audit(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "TENANT_ENFORCEMENT_ENABLED", True)
    default_tenant = await db_session.get(Tenant, DEFAULT_TENANT_ID)
    assert default_tenant is not None
    platform_admin, admin_headers = await _headers(
        client, db_session, default_tenant, role="platform_admin"
    )
    tenant_b = await _tenant(db_session, f"b-{uuid.uuid4().hex[:6]}")
    _, headers_b = await _headers(client, db_session, tenant_b)
    ds_b = await _datasource(client, headers_b, "tenant-b-ds")

    switched = await client.get(
        f"{BASE}/datasources",
        headers={**admin_headers, "X-Tenant-Id": str(tenant_b.id)},
    )
    assert switched.status_code == 200, switched.text
    assert {item["id"] for item in switched.json()["items"]} == {ds_b}

    audit = await db_session.scalar(
        select(AuditLog)
        .where(
            AuditLog.user_id == platform_admin.id,
            AuditLog.action == "tenant.cross_access",
        )
        .order_by(AuditLog.id.desc())
    )
    assert audit is not None
    assert audit.tenant_id == tenant_b.id
    assert (audit.details or {})["target_tenant_id"] == str(tenant_b.id)

    # sentinel 不可作为普通租户切入口
    response = await client.get(
        f"{BASE}/datasources",
        headers={**admin_headers, "X-Tenant-Id": str(PLATFORM_TENANT_ID)},
    )
    assert response.status_code == 404

    # 不存在/停用租户 → 404
    response = await client.get(
        f"{BASE}/datasources",
        headers={**admin_headers, "X-Tenant-Id": str(uuid.uuid4())},
    )
    assert response.status_code == 404

    suspended = await _tenant(db_session, f"s-{uuid.uuid4().hex[:6]}")
    suspended.status = "suspended"
    await db_session.flush()
    response = await client.get(
        f"{BASE}/datasources",
        headers={**admin_headers, "X-Tenant-Id": str(suspended.id)},
    )
    assert response.status_code == 404


async def test_platform_tenant_hidden_from_customer_scope(db_session) -> None:
    customers = list(
        (
            await db_session.scalars(
                select(Tenant).where(Tenant.kind == "customer", Tenant.status == "active")
            )
        ).all()
    )
    assert all(tenant.id != PLATFORM_TENANT_ID for tenant in customers)
    assert (
        await db_session.scalar(select(Tenant).where(Tenant.id == PLATFORM_TENANT_ID))
    ).kind == "platform"
