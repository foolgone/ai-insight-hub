"""骨架冒烟测试：验证应用可启动、健康检查可用。

随功能开发不断扩充；当前仅覆盖系统接口。
"""
import pytest

pytestmark = pytest.mark.unit


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_api_v1_health(client):
    """业务前缀下的健康检查（默认 /api/v1/health）"""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
