# M4-A staging flag=true 冒烟 runbook

> 状态：`planned`（未执行；等待 staging 可访问与排期）
> 范围：**仅 staging**；不生产、不导入真实客户数据
> 前置：PR-3 accepted for local/test（`e2eaebd`）
> **本地真实栈冒烟只证明代码路径，不替代 staging 结论。**

## 1. 前置条件

| 项 | 要求 |
|---|---|
| 代码 | 包含 023 / 024 / 025 的提交（PR-3 合并后） |
| staging DB | 可备份、可回滚；禁止直接使用生产库 |
| staging 对象存储 | bucket / 本地目录可备份；记录 bucket 名称 |
| 测试账号 | 两个测试租户 + 各一个测试用户；不使用真实客户数据 |
| flag | 初始 `TENANT_ENFORCEMENT_ENABLED=false` |
| 变更窗口 | 与运维确认；窗口内可重启 API / worker |

## 2. 备份

```bash
# DB（示例，按 staging 实际连接串替换）
pg_dump -Fc "$STAGING_DATABASE_URL" -f m4a_staging_before_025.dump

# 对象存储：记录 bucket 前缀清单，按 staging 工具做快照/版本备份
# 本地存储：tar 备份 STORAGE_LOCAL_DIR
```

备份完成后先做一次恢复演练（恢复到临时库/临时目录），确认可用再继续。

## 3. 迁移

```bash
cd backend
export DATABASE_URL="$STAGING_DATABASE_URL"
alembic current                 # 记录起点
alembic upgrade head            # 023 -> 024 -> 025
alembic current                 # 记录终点：025
```

迁移后检查：

```sql
-- 15 张业务表 tenant_id 无默认值
SELECT table_name, column_default
FROM information_schema.columns
WHERE table_schema='public' AND column_name='tenant_id'
ORDER BY table_name;
-- 业务表 column_default 必须为 NULL；audit_logs/llm_calls 允许 NULL

-- 回填审计：0 NULL / 0 父子不一致（示例，完整清单见写入路径文档）
SELECT count(*) FROM data_sources WHERE tenant_id IS NULL;
SELECT count(*) FROM tasks WHERE tenant_id IS NULL;
SELECT count(*) FROM reports WHERE tenant_id IS NULL;
```

## 4. 开启 flag

```bash
export TENANT_ENFORCEMENT_ENABLED=true
# 重启 API 与所有 Celery worker（含 -Q clean 的 worker）
```

确认两个进程都读取到新值后，再开始业务冒烟。

## 5. 冒烟步骤

使用两个测试租户 A / B：

| # | 操作 | 预期 |
|---|---|---|
| 1 | A 注册 / 登录 | 成功；token 带 tenant A |
| 2 | A 建数据源 | 201，`data_sources.tenant_id=A` |
| 3 | A 上传 CSV | 202；key 为 `tenant/A/uploads/<datasource>/...` |
| 4 | 等待清洗任务 | `completed`；`cleaned_data.tenant_id=A` |
| 5 | A 生成报告 | `completed`；key 为 `tenant/A/reports/<report>.md` |
| 6 | A 用旧 key 报告下载 | 200（旧 key 兼容） |
| 7 | B 下载 A 的新/旧报告 | 404 |
| 8 | B 读取 A 的 raw-data 列表 | 404 |
| 9 | B 读取 A 的数据源 | 404 |
| 10 | A 的 `/tenants` | 只返回 A 自己的租户；不含 platform sentinel / B |
| 11 | 记录 Run / Task / Report / object key | 见下表 |

证据表（贴 staging 实际值）：

| 项 | 值 |
|---|---|
| 迁移前 revision | |
| 迁移后 revision | |
| 测试租户 A / B | |
| 上传 object key | |
| 报告 file_path | |
| 清洗 Task id / status | |
| 报告 Task id / status | |
| 跨租户 404 路径 | |
| flag 值 | true |

## 6. 回滚演练（同一窗口）

按 `06-m4a-rollback-runbook.md` 顺序执行：

1. `TENANT_ENFORCEMENT_ENABLED=false`，重启 API/worker；
2. 验证旧单租户流程（登录、数据源、上传、报告）；
3. `alembic downgrade c1d5f8a3e7b2`（025 -> 024，恢复 server_default）；
4. 验证 15 张业务表 `column_default` 恢复；
5. **不清对象、不删 tenant**；
6. 记录回滚耗时与验证结果。

## 7. 结论

- 只有上述 1–6 全部通过，才形成“staging flag=true smoke 通过”的结论。
- 当前状态：**未执行**；需运维提供 staging 访问与窗口后按本 runbook 排期。
- 生产 migration 仍单独评审，不随本 runbook 自动放行。
