# M4-A 回滚 runbook（顺序固定）

> 状态：`draft`（待 staging 演练）
> 适用：PR-3 / 025 已上 staging，需回退到单租户兼容状态
> 原则：**先关 flag，再降级 025；不清对象、不删 tenant。**

## 1. 固定顺序（不得调整）

| 步骤 | 动作 | 为什么 |
|---|---|---|
| 1 | `TENANT_ENFORCEMENT_ENABLED=false`，重启 API 与所有 Celery worker | 先停止跨租户强制，避免 025 降级期间新旧代码行为不一致 |
| 2 | 验证单租户流程：登录、数据源列表、上传、报告下载 | 确认 flag=false 行为恢复 |
| 3 | 备份当前 DB（回滚前快照） | 保留回滚前状态，便于再次前进 |
| 4 | `alembic downgrade c1d5f8a3e7b2` | 025 -> 024，恢复 15 张业务表 `tenant_id` server_default |
| 5 | 验证 15 张业务表 `column_default` 恢复默认租户 | 确认旧代码可在缺 tenant 时写入 |
| 6 | 再跑一次单租户冒烟（上传/清洗/报告） | 确认降级后旧流程可用 |
| 7 | 记录耗时、revision、验证结果 | 回滚证据 |

## 2. 禁止事项

- 禁止先 downgrade 再关 flag。
- 禁止删除对象存储文件、`raw_data` / `reports` / `cleaned_data` 行。
- 禁止删除 `tenants` 或重置 `tenant_id`。
- 禁止在回滚中顺带 downgrade 024 / 023；如确需继续回退，单独评审并重新备份。
- 禁止用本地冒烟替代 staging 回滚演练。

## 3. 命令

```bash
cd backend
export DATABASE_URL="$STAGING_DATABASE_URL"

# 1) 先关 flag（环境变量/配置中心），重启 API 与 worker
export TENANT_ENFORCEMENT_ENABLED=false

# 2) 验证单租户流程后，备份
pg_dump -Fc "$STAGING_DATABASE_URL" -f m4a_staging_before_rollback.dump

# 3) 只降 025
alembic downgrade c1d5f8a3e7b2
alembic current

# 4) 验证默认值恢复
psql "$STAGING_DATABASE_URL" -c "
SELECT table_name, column_default
FROM information_schema.columns
WHERE table_schema='public' AND column_name='tenant_id'
ORDER BY table_name;"
```

## 4. 验证清单

| 项 | 通过标准 |
|---|---|
| flag=false | API / worker 环境变量均为 false，重启完成 |
| 单租户流程 | 登录、数据源、上传、清洗、报告下载正常 |
| 025 降级 | `alembic current` = `c1d5f8a3e7b2` |
| 默认值 | 15 张业务表 `column_default` 指向默认租户 |
| 数据保留 | 对象、`tenant_id`、租户行均未删除 |
| 再前进 | 如需恢复：备份后 `alembic upgrade head`，再按 staging runbook 开 flag |

## 5. 演练记录模板

| 项 | 值 |
|---|---|
| 演练日期 / 执行人 | |
| 迁移前 revision | |
| 回滚后 revision | |
| flag 关闭时间 | |
| 025 downgrade 耗时 | |
| 单租户冒烟结果 | |
| 异常 / 处理 | |
