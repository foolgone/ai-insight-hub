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

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """FastAPI 测试客户端（不依赖数据库，可测健康检查等纯接口）"""
    with TestClient(app) as c:
        yield c
