# 本地全量测试：隔离测试库

> 状态：P1-5；目标：本地全量 pytest **不读写 `aiinsight` dev 库**，结果可复现。
> 日期：2026-11-25
> 相关：`backend/scripts/run_tests_local.py`、`backend/tests/conftest.py`

## 1. 一键命令（推荐）

在 `backend/` 下：

```powershell
# Windows
.\venv\Scripts\python.exe scripts\run_tests_local.py

# Linux / macOS
./venv/bin/python scripts/run_tests_local.py
```

默认执行 `pytest -m "not prompt"`；可追加 pytest 参数：

```powershell
.\venv\Scripts\python.exe scripts\run_tests_local.py -- tests/unit -q
```

## 2. 脚本做了什么

| 步骤 | 行为 |
|---|---|
| 选库 | 从 `backend/.env` 的 `DATABASE_URL` 派生；库名固定为 `aiinsight_test`（已是 `*_test` 则保留）。 |
| 建库 | 测试库不存在时自动创建（连接 maintenance DB `postgres`）。 |
| 重置 | `DROP SCHEMA public CASCADE` + `CREATE SCHEMA public`，清空旧测试数据。 |
| 迁移 | `alembic upgrade head`，迁移测试在干净库上执行。 |
| Redis | 默认使用同一 Redis 实例的 **DB 15**；端口为 6380 时直接用 0。启动前 `FLUSHDB`。 |
| 测试 | `pytest -m "not prompt"`，`DATABASE_URL` / `REDIS_URL` 注入子进程。 |

> 测试库是可丢弃的；**不要把 `TEST_DATABASE_URL` 指向生产或 dev 库**。

## 3. 环境变量

| 变量 | 作用 | 示例 |
|---|---|---|
| `TEST_DATABASE_URL` | 显式指定测试库；不设置时从 `DATABASE_URL` 派生 | `postgresql://aiinsight:dev_password@192.168.150.100:5433/aiinsight_test` |
| `TEST_REDIS_URL` | 显式指定测试 Redis | `redis://192.168.150.100:6380/0` 或 `redis://192.168.150.100:6379/15` |

本地 VM 联调默认值（从 `backend/.env` 派生）：

```text
PostgreSQL: 192.168.150.100:5433 / aiinsight_test
Redis:      192.168.150.100:6379 / DB 15
```

## 4. 防污染守卫

`backend/tests/conftest.py` 对 **integration / security** 测试（或使用 `db_session` 的用例）做库名检查：

- 只允许库名以 `_test` 结尾；
- 否则直接 `pytest.exit`，提示使用 `scripts/run_tests_local.py` 或设置 `TEST_DATABASE_URL`；
- 单元测试（不依赖 DB）不受影响，可直接 `pytest tests/unit -q`。
- 2026-11-25 实测：直接 `pytest tests/integration/test_digest.py`（dev 库）被守卫拒绝。

这样即使误用 `pytest -m "not prompt"`，也不会读写 `aiinsight` dev 库。

## 5. 验收记录（P1-5）

| 项 | 结果 |
|---|---|
| 测试库 | `aiinsight_test` @ `192.168.150.100:5433`，脚本自动建库/重置/迁移 |
| Redis | `192.168.150.100:6379/15`，测试前 FLUSHDB |
| 第一次全量 | ✅ **1138 passed / 255 deselected**，5m50s，exit 0 |
| 第二次全量 | ✅ **1138 passed / 255 deselected**，5m16s，exit 0 |
| dev 库 | ✅ 未读写；守卫拒绝 `aiinsight` |
| CI | 仍使用 `aiinsight_test`；P1-3b 提交 CI 全绿 |

## 6. 常见问题

- **建库失败 `permission denied to create database`**：让 DBA 预建 `aiinsight_test`，或给测试账号 `CREATEDB`；脚本检测到库已存在会跳过创建。
- **迁移 001 扩展失败**：重置 schema 会删除 `public` 下的对象；迁移会重新 `CREATE EXTENSION IF NOT EXISTS vector/pg_trgm`。若扩展记录残留导致失败，删除并重建测试库即可。
- **想保留测试数据复跑**：加 `--no-reset`（不推荐用于验收）。
- **CI 不需要脚本**：workflow 已用 `POSTGRES_DB=aiinsight_test` 且执行 `alembic upgrade head`。
