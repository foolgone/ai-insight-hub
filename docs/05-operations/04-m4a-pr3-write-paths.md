# M4-A PR-3：写入路径清单 / 存储前缀 / 025 说明

> 状态：`implemented / verified`（2026-11-26，待验收）；后端全量 1163 passed；本地真实栈 flag=true 冒烟通过
> 上游：`docs/05-operations/02-m4a-tenant-first-scope.md`（scope approved）
> 范围：存储 tenant 前缀、旧 key 双读、025 移除业务表默认租户、负向写入测试
> 不做：retention、alerting、cost 预算、RLS、生产 migration

## 1. 存储 key

| 场景 | 新写入 key | 兼容 |
|---|---|---|
| 上传文件 | `tenant/<tenant_id>/uploads/<datasource_id>/<uuid>_<filename>` | 旧对象保留 `<datasource_id>/<uuid>_<filename>`，读取按 `raw_data.file_info.object_name` 原样访问 |
| 报告文件 | `tenant/<tenant_id>/reports/<report_id>.<ext>` | 旧报告保留 `reports/<report_id>.<ext>`，下载按 `report.file_path` 原样访问 |

- 新写入必须带 `tenant_id`：`storage_service.save_upload` / `save_upload_from_path` 的 `tenant_id` 为必填参数。
- `save_bytes` 用于报告等生成物，由调用方拼 key；PR-3 后报告统一 tenant 前缀。
- 批量搬迁不在本 PR；旧 key 继续可读，迁移任务另开。

## 2. 025 migration

- 移除 15 张业务表的 `tenant_id` `server_default`：
  `users`、`data_sources`、`raw_data`、`cleaned_data`、`analysis_results`、
  `knowledge_base`、`knowledge_gaps`、`tasks`、`reports`、`qa_datasets`、
  `qa_dataset_versions`、`qa_dataset_items`、`rag_traces`、
  `rag_evaluation_runs`、`rag_evaluation_results`。
- 保留 `NOT NULL` / 外键；`audit_logs` / `llm_calls` 保持 nullable（平台级）。
- `downgrade` 恢复默认租户 `server_default`，仅供回滚；新代码不得依赖。
- 测试：`test_migration_025` 覆盖默认值移除、缺 tenant 的 DB 写入拒绝、up/down 两次。

## 3. 写入路径清单（025 前盘点）

| 入口 / 任务 | 写入表 | tenant 来源 |
|---|---|---|
| `POST /auth/register` | `users` | 显式 `DEFAULT_TENANT_ID`（公开注册当前落默认租户） |
| `POST /datasources` | `data_sources` | 用户 TenantContext（flag=false 为 `user.tenant_id`） |
| `POST /datasources/{id}/upload` | `raw_data` + `tasks` | `datasource.tenant_id` / 用户上下文 |
| 清洗任务 | `tasks` + `cleaned_data` | 用户上下文创建任务；`raw.tenant_id` 写清洗结果 |
| 转写切分任务 | `tasks` + `knowledge_base` + `analysis_results` | `raw.tenant_id` |
| 质量评估任务 | `tasks` + `analysis_results` | 用户上下文创建任务；`task.tenant_id` 写结果 |
| 洞察任务 | `tasks` + `analysis_results` | 用户上下文创建任务；`task.tenant_id` 写结果 |
| 知识提取任务 | `tasks` + `knowledge_base` + `knowledge_gaps` | 用户上下文创建任务；`task.tenant_id` 写子资源 |
| 种子知识 | `knowledge_base` | `datasource.tenant_id`（`seed_knowledge` 显式参数） |
| `POST /datasources/{id}/reports` | `reports` + `tasks` | 用户上下文创建报告；`report.tenant_id` 建任务与文件 |
| 报告生成 | `reports` 状态 + 报告文件 | `report.tenant_id` |
| QA 数据集创建 / 版本 / 导入 | `qa_datasets` / `qa_dataset_versions` / `qa_dataset_items` | 用户上下文创建数据集；版本/条目继承 `dataset/version.tenant_id` |
| RAG 查询 | `rag_traces` | 条目所属数据集 tenant；无条目时用用户上下文 |
| RAG 批量评测创建 / 重试 | `tasks` + `rag_evaluation_runs` | `dataset.tenant_id` / 父 Run `tenant_id` |
| RAG 评测执行 | `rag_evaluation_results`、Run/Task 状态 | `run.tenant_id` |
| 跨租户审计 | `audit_logs` | 目标 tenant（平台级，允许 NULL） |
| LLM 调用记账 | `llm_calls` | 用户/父资源 tenant（平台级，允许 NULL） |
| `scripts/seed_demo.py` | 数据源/原始/清洗/分析/知识/报告 | 持久化 user/datasource 的 `tenant_id` |
| `scripts/seed_rag_eval*.py` | 数据集/版本/条目 | 用户 `tenant_id` + 显式 `system_context` |
| 测试工厂 | 各业务表 | `DEFAULT_TENANT_ID`（可显式覆盖） |

## 4. flag 语义

| `TENANT_ENFORCEMENT_ENABLED` | 无 TenantContext 时 |
|---|---|
| `false`（默认） | 允许，读写按 `user.tenant_id`，保持单租户行为 |
| `true` | 抛 `TENANT_CONTEXT_MISSING`（500），不落默认租户 |

- API：`get_current_user` 统一 attach context；platform_admin 切租户校验 `customer + active`。
- Celery / CLI：必须显式 attach：
  - RAG 评测执行器用 `system_context(run.tenant_id)`；
  - seed 脚本用 `system_context(user.tenant_id)`。
- 负向测试：`test_flag_true_write_without_context_does_not_fall_back` 直接调用 service，断言 `TenantContextMissingError` 且无 Task 行落库。

## 5. 验收命令

```bash
cd backend
python scripts/run_tests_local.py tests/integration/test_migration_025.py \
  tests/integration/test_tenant_enforcement.py \
  tests/integration/test_upload_clean.py \
  tests/integration/test_reports_api.py \
  tests/unit/test_storage.py -q
python scripts/run_tests_local.py          # 全量
alembic check                               # 需在 aiinsight_test 上执行
```

## 6. 验证记录（2026-11-26）

| 项 | 结果 |
|---|---|
| 025 默认值 | 15 张业务表 `column_default` 为空；downgrade 恢复默认租户；up/down 两次通过 |
| 缺 tenant 写入 | DB `NOT NULL` 拒绝；flag=true 无 context 时 `TENANT_CONTEXT_MISSING`，无 Task 落库 |
| 新上传 key | `tenant/<default>/uploads/<datasource_id>/...`（集成测试 + 真实栈冒烟） |
| 新报告 key | `tenant/<default>/reports/<report_id>.md`（集成测试 + 真实栈冒烟） |
| 旧 key | 存储层按原 key 读取；旧报告 `reports/<id>.md` 仍可下载 |
| 跨租户 | flag=true 下 GET 他租户数据源 → 404；租户列表不含他租户 |
| 全量 | **1163 passed / 255 deselected**；black / flake8 / mypy / import-linter / alembic check 通过 |
| 真实栈冒烟 | 本地 API + Celery（flag=true）：注册、建数据源、上传、清洗完成、报告完成、跨租户 404、tenant 前缀全部通过 |

> staging 环境在当前会话不可访问；未对其执行 migration 或开启 flag。合并/验收后需在 staging 用同一 runbook 执行一次 flag=true 冒烟，再决定生产 migration 是否单独批准。

