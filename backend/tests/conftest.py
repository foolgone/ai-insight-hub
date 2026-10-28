"""pytest 全局 fixture。

分层约定（详见 docs/06-testing/00-测试策略总览.md）：
- 单元测试：不依赖外部服务，用 mock 隔离 LLM/DB
- 集成测试：需要真实 PostgreSQL/Redis（docker-compose.test.yml）
"""
import sys
from pathlib import Path

import pytest

# 保证 `app` 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def disable_rate_limit_by_default(monkeypatch) -> None:
    """测试默认关闭限流：仅限流用例显式开启，避免 Redis/事件循环耦合。"""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)


@pytest.fixture(autouse=True)
def allow_server_key_fallback_in_tests(monkeypatch) -> None:
    """测试环境默认允许回退服务端 Key（BYOK 守门用例自行改回 False）。

    存量集成用例用无凭据的 ``test_user`` 打 AI 触发端点并断言 202；
    默认 ``ALLOW_SERVER_KEY_FALLBACK=False`` 会让它们集体变 428。
    """
    monkeypatch.setattr(settings, "ALLOW_SERVER_KEY_FALLBACK", True)


@pytest.fixture()
def client():
    """FastAPI 测试客户端（不依赖数据库，可测健康检查等纯接口）"""
    with TestClient(app) as c:
        yield c
