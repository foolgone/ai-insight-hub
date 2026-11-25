"""本地全量测试：固定使用隔离测试库，避免共享 dev DB 污染。

做的事情：

1. 从 ``backend/.env`` / 环境变量读取 ``DATABASE_URL``，把库名换成
   ``aiinsight_test``（已是 ``*_test`` 则保持不变）；
2. 如测试库不存在则创建；
3. 重置 ``public`` schema，再执行 ``alembic upgrade head``；
4. Redis 默认切到同一实例的 DB 15（或显式 ``TEST_REDIS_URL``）并 flush；
5. 运行 ``pytest -m "not prompt"``。

用法（在 ``backend/`` 下）::

    .\\venv\\Scripts\\python.exe scripts\\run_tests_local.py
    .\\venv\\Scripts\\python.exe scripts\\run_tests_local.py -- tests/unit -q

覆盖连接串::

    TEST_DATABASE_URL=postgresql://user:pass@host:port/aiinsight_test
    TEST_REDIS_URL=redis://host:6380/0
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DB = "aiinsight_test"
REDIS_TEST_DB_INDEX = 15


def _dotenv() -> dict[str, str]:
    values = dotenv_values(BACKEND_DIR / ".env")
    return {key: value for key, value in values.items() if value is not None}


def _pick(env: dict[str, str], key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or env.get(key) or default


def _test_database_url(base_url: str) -> URL:
    url = make_url(base_url)
    if not url.database:
        raise SystemExit(f"DATABASE_URL 缺少库名：{base_url!r}")
    if url.database.endswith("_test"):
        return url
    return url.set(database=DEFAULT_TEST_DB)


def _sync_url(url: URL) -> URL:
    return url.set(drivername="postgresql+psycopg2")


def _async_url(url: URL) -> URL:
    return url.set(drivername="postgresql+asyncpg")


def _check_identifier(name: str | None) -> str:
    if not name or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SystemExit(f"非法测试库名：{name!r}")
    return name


def _ensure_database(test_url: URL) -> bool:
    """测试库不存在则创建；返回是否新建。"""
    database = _check_identifier(test_url.database)
    if not database.endswith("_test"):
        raise SystemExit(f"拒绝使用非测试库：{database}")
    maintenance = test_url.set(database="postgres")
    engine = create_engine(_sync_url(maintenance), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database},
            ).scalar()
            if exists:
                return False
            conn.execute(text(f'CREATE DATABASE "{database}"'))
            return True
    finally:
        engine.dispose()


def _reset_schema(test_url: URL) -> None:
    engine = create_engine(_sync_url(test_url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def _test_redis_url(base_url: str | None) -> str:
    if not base_url:
        return "redis://localhost:6379/15"
    url = make_url(base_url)
    if url.port == 6380:
        return url.render_as_string(hide_password=False)
    return url.set(database=str(REDIS_TEST_DB_INDEX)).render_as_string(hide_password=False)


def _flush_redis(redis_url: str) -> None:
    try:
        import redis
    except ImportError:
        print("[warn] 未安装 redis，跳过测试 Redis 清理")
        return
    try:
        client = redis.from_url(redis_url)
        client.flushdb()
    except Exception as exc:  # noqa: BLE001 - 清理失败不阻断，pytest 会暴露真实问题
        print(f"[warn] 测试 Redis 清理失败：{exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend tests on an isolated test DB")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="保留测试库 schema（默认每次重置 schema 后重新迁移）",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help='传给 pytest 的参数（默认 -m "not prompt"）',
    )
    args = parser.parse_args()

    env_file = _dotenv()
    base_url = _pick(env_file, "TEST_DATABASE_URL") or _pick(env_file, "DATABASE_URL")
    if not base_url:
        raise SystemExit("未找到 DATABASE_URL / TEST_DATABASE_URL（检查 backend/.env）")
    test_url = _test_database_url(base_url)
    redis_url = _test_redis_url(_pick(env_file, "TEST_REDIS_URL") or _pick(env_file, "REDIS_URL"))

    created = _ensure_database(test_url)
    if not args.no_reset:
        _reset_schema(test_url)

    env = os.environ.copy()
    env["DATABASE_URL"] = _async_url(test_url).render_as_string(hide_password=False)
    env["REDIS_URL"] = redis_url
    _flush_redis(redis_url)

    print(
        "[test-db] "
        f"db={test_url.database}@{test_url.host}:{test_url.port} "
        f"created={created} reset={not args.no_reset} "
        f"redis={make_url(redis_url).render_as_string(hide_password=True)}"
    )

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        stderr=subprocess.STDOUT,
    )
    pytest_args = args.pytest_args or ["-m", "not prompt"]
    return subprocess.run(
        [sys.executable, "-m", "pytest", *pytest_args],
        cwd=BACKEND_DIR,
        env=env,
        stderr=subprocess.STDOUT,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
