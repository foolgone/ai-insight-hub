# M4-A 生产 migration 变更单（模板，未批准）

> 状态：`draft / not approved`
> 变更：生产 `alembic upgrade head`（含 023 / 024 / 025）
> **不得随 PR 合并自动上生产；必须单独评审、单独签字。**
> 适用条件：staging flag=true 冒烟通过 + 回滚演练通过 + 本变更单签字。

## 1. 基本信息

| 项 | 内容 |
|---|---|
| 变更编号 | （待填） |
| 申请人 / 执行人 | |
| 评审人 / 批准人 | |
| 计划窗口 | （待填，含开始/结束/回滚截止） |
| 目标环境 | production |
| 影响服务 | API、Celery worker、对象存储读取 |
| 预计停机 | 迁移本身无长锁；重启 API/worker 期间短时不可用 |
| 回滚方案 | `06-m4a-rollback-runbook.md` |

## 2. 变更前检查（全部必须）

| 项 | 命令 / 证据 | 通过标准 |
|---|---|---|
| 当前 revision | `alembic current` | 记录起点 |
| 备份 | `pg_dump -Fc ...` | 备份文件校验可读 |
| 恢复演练 | 恢复到临时库并启动只读检查 | 表结构/行数抽样一致 |
| 对象备份 | bucket/version 或本地目录快照 | 记录快照 ID |
| tenant 审计 | 下方 SQL | **0 NULL / 0 mismatch** |
| 监控 | API 5xx、任务失败率、DB 连接、存储错误 | 窗口内可观测 |
| 告警 | 值班人 / 通知渠道 | 已确认 |
| 回滚包 | 025 downgrade 已在 staging 演练通过 | 记录 staging 演练日期 |

### 2.1 tenant 回填审计 SQL

```sql
-- 1) 业务表 tenant_id 不允许 NULL
SELECT 'users' t, count(*) FROM users WHERE tenant_id IS NULL
UNION ALL SELECT 'data_sources', count(*) FROM data_sources WHERE tenant_id IS NULL
UNION ALL SELECT 'raw_data', count(*) FROM raw_data WHERE tenant_id IS NULL
UNION ALL SELECT 'cleaned_data', count(*) FROM cleaned_data WHERE tenant_id IS NULL
UNION ALL SELECT 'analysis_results', count(*) FROM analysis_results WHERE tenant_id IS NULL
UNION ALL SELECT 'knowledge_base', count(*) FROM knowledge_base WHERE tenant_id IS NULL
UNION ALL SELECT 'knowledge_gaps', count(*) FROM knowledge_gaps WHERE tenant_id IS NULL
UNION ALL SELECT 'tasks', count(*) FROM tasks WHERE tenant_id IS NULL
UNION ALL SELECT 'reports', count(*) FROM reports WHERE tenant_id IS NULL
UNION ALL SELECT 'qa_datasets', count(*) FROM qa_datasets WHERE tenant_id IS NULL
UNION ALL SELECT 'qa_dataset_versions', count(*) FROM qa_dataset_versions WHERE tenant_id IS NULL
UNION ALL SELECT 'qa_dataset_items', count(*) FROM qa_dataset_items WHERE tenant_id IS NULL
UNION ALL SELECT 'rag_traces', count(*) FROM rag_traces WHERE tenant_id IS NULL
UNION ALL SELECT 'rag_evaluation_runs', count(*) FROM rag_evaluation_runs WHERE tenant_id IS NULL
UNION ALL SELECT 'rag_evaluation_results', count(*) FROM rag_evaluation_results WHERE tenant_id IS NULL;

-- 2) 父子 tenant 一致性（全部必须为 0）
SELECT count(*) FROM raw_data c JOIN data_sources p ON p.id=c.datasource_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM cleaned_data c JOIN data_sources p ON p.id=c.datasource_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM analysis_results c JOIN data_sources p ON p.id=c.datasource_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM knowledge_base c JOIN data_sources p ON p.id=c.datasource_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM knowledge_gaps c JOIN data_sources p ON p.id=c.datasource_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM qa_dataset_versions c JOIN qa_datasets p ON p.id=c.dataset_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM qa_dataset_items c JOIN qa_dataset_versions p ON p.id=c.version_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
SELECT count(*) FROM rag_evaluation_results c JOIN rag_evaluation_runs p ON p.id=c.run_id
  WHERE c.tenant_id IS DISTINCT FROM p.tenant_id;
```

> 任一项非 0：停止变更，先修复数据，不得执行 025。

## 3. 变更步骤

```bash
cd backend
export DATABASE_URL="$PROD_DATABASE_URL"

# 1) 再次确认 revision 与备份
alembic current

# 2) 只跑 migration（不自动开 flag）
alembic upgrade head
alembic current
```

| 步骤 | 操作 | 预计 |
|---|---|---|
| 1 | 进入维护窗口，停止写入（如可） | 5 min |
| 2 | 执行 `alembic upgrade head` | 5–15 min |
| 3 | 校验 revision = 025、15 张表 default 为空 | 2 min |
| 4 | 重启 API / Celery worker（加载新代码与配置） | 5 min |
| 5 | 保持 `TENANT_ENFORCEMENT_ENABLED=false`，先跑单租户 smoke | 10 min |
| 6 | 业务确认后，按单独审批决定是否开 flag | 另行审批 |

> 025 只删默认值，不改变数据；**flag 开启是独立变更**，不在本变更单自动执行。

## 4. 变更后 smoke

| 项 | 预期 |
|---|---|
| `/health` | 200 |
| 登录 / 数据源 / 上传 / 清洗 / 报告 | 正常（flag=false） |
| 新上传 object key | `tenant/<tenant_id>/uploads/...` |
| 新报告 file_path | `tenant/<tenant_id>/reports/...` |
| 旧对象读取 | 正常 |
| 任务失败率 / 5xx | 无异常上升 |
| `server_default` | 15 张业务表为 NULL |
| tenant 审计 | 仍为 0 NULL / 0 mismatch |

## 5. 监控（窗口内 + 窗口后 24h）

| 指标 | 阈值 / 动作 |
|---|---|
| API 5xx | 连续 5 分钟高于基线 → 回滚 |
| Celery 任务失败率 | 明显上升 → 暂停写入/回滚 |
| DB 连接 / 慢查询 | 异常 → 检查锁与迁移 |
| 对象存储错误 | 上升 → 检查 key/权限，不回退数据 |
| 租户越权告警 | 任意 → 立即关 flag 并排查 |

## 6. 回滚触发与执行

触发条件：

- tenant 审计非 0；
- 迁移后 smoke 失败且 10 分钟内无法修复；
- 5xx / 任务失败率持续超阈值；
- 发现跨租户访问。

执行：按 `06-m4a-rollback-runbook.md`，**先 flag=false，再 downgrade 025**；不清对象、不删 tenant。

## 7. 签字

| 角色 | 姓名 | 结论 | 日期 |
|---|---|---|---|
| 开发负责人 | | | |
| 运维负责人 | | | |
| 数据/安全（如适用） | | | |
| 最终批准 | | | |

> 当前状态：**未提交生产审批**。只有 staging 冒烟、回滚演练、备份恢复演练、监控与 tenant 审计全部通过后，才进入本变更单签字。
