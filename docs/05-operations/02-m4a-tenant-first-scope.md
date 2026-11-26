# M4-A tenant-first：实现 scope / design

> 状态：`scope_approved`（2026-11-25）；PR-1 / PR-2 accepted；**PR-3 已实现/验证，待验收**
> 前置决策：`docs/05-operations/03-m4a-pr2-decisions.md`
> 日期：2026-11-25
> 上游：`docs/05-operations/01-m4a-constraints-decision.md`（accepted baseline）
> 边界：**本文件不写 migration、不改代码、不碰生产**；只定义 tenant 切片。
> 目标：先完成租户隔离，不把 audit / retention / alerting / cost / data-rights 混进同一 PR。

## 1. 现状事实（核对结果）

| 项 | 现状 |
|---|---|
| 租户 | 无 `tenants` 表；所有资源按 `user_id` 或父资源归属 |
| JWT claims | `sub` / `role` / `type` / `jti` / `iat` / `exp`，无 `tenant_id` |
| 角色 | `admin` / `user` / `viewer`（`users.role` CHECK；`require_roles` 按 DB 角色） |
| 存储 | 上传：`<datasource_id>/<uuid>_<filename>`；报告：`reports/<report_id>.<ext>`；共享 bucket，无租户前缀 |
| 归属 | `DataSource` / `Report` / `Task` / `QaDataset` / `RagTrace` / `RagEvaluationRun` 有 `user_id`；子表靠 `datasource_id` / `version_id` / `run_id` |
| 失败明细 | **没有 `rag_evaluation_failures` 物理表**；`/failures` 是对 `rag_evaluation_results(status='failed')` 的筛选，租户随 Run/Result |
| 后台任务 | digest / cost monitor / stale run recovery / cleanup 存在跨用户聚合查询 |
| 报告 | 复用报告中心；下载按 `report.file_path` 读取对象，已有查看/下载归属校验 |

## 2. 目标与非目标

### 2.1 本切片目标

1. 建 `tenants` + 默认租户；所有核心业务表带 `tenant_id` 并回填。
2. JWT 带 `tenant_id`；新增 `platform_admin` / `tenant_admin` 角色。
3. 跨租户资源访问统一 **404**，不泄露存在性。
4. Repository / service 查询强制 tenant scope；后台任务显式租户上下文。
5. 存储 key 使用 `tenant/<tenant_id>/...`；历史对象兼容读取。
6. `TENANT_ENFORCEMENT_ENABLED` 默认 false，staging 先开，可回滚。
7. 迁移 up/down 在 `aiinsight_test` 验证；生产 migration 单独批准。

### 2.2 明确不做

- 不做审计不可篡改 / hash chain / 审计查询界面（仅 platform_admin 跨租户操作写现有 `audit_logs`）。
- 不做保留期 purge、Alertmanager、成本预算、数据权利（导出/删除/脱敏）产品化。
- 不做租户管理 UI / 计费 / 配额；tenants 仅最小字段。
- 不做 RLS（本期应用层强制；是否加 RLS 列为开放决策）。
- 不改 M1 / Judge / target / Prompt；不跑 10/40。

## 3. 数据模型与完整表清单

### 3.1 新表 `tenants`

| 字段 | 说明 |
|---|---|
| `id` UUID PK | 默认租户使用固定 UUID（迁移常量，便于回填/测试） |
| `name` varchar(100) | 租户名称 |
| `slug` varchar(50) unique | URL/运维标识 |
| `status` varchar(20) | `active` / `suspended`（默认 active） |
| `created_at` / `updated_at` | 时间戳 |

默认租户：`slug='default'`，迁移内插入；`DEFAULT_TENANT_ID` 以代码常量 + 可选环境变量覆盖。

### 3.2 核心表（本切片必须覆盖）

| 表 | 现有归属/父级 | `tenant_id` 回填来源 | 强制点 |
|---|---|---|---|
| `users` | 自身 | 默认租户（所有存量用户） | 登录 / JWT / 用户管理 |
| `data_sources` | `user_id` | `users.tenant_id` | 列表/详情/更新/删除 |
| `raw_data` | `datasource_id` | 父 `data_sources.tenant_id` | 上传/读取/转写 |
| `cleaned_data` | `datasource_id` | 父 `data_sources` | 清洗/质量/报告 |
| `analysis_results` | `datasource_id` | 父 `data_sources` | 质量/洞察 |
| `knowledge_base` | `datasource_id` | 父 `data_sources` | 知识列表/详情/导入 |
| `knowledge_gaps` | `datasource_id` | 父 `data_sources` | 盲区 |
| `tasks` | `user_id` / `datasource_id` | 优先 `user_id`，否则父 datasource；再否则默认租户 | 列表/取消/重试/进度 |
| `reports` | `user_id` / `datasource_id` | 优先 `user_id`，否则父 datasource | 列表/详情/下载/删除 |
| `qa_datasets` | `user_id` | `users.tenant_id` | 数据集 CRUD |
| `qa_dataset_versions` | `dataset_id` | 父 dataset | 版本创建/发布 |
| `qa_dataset_items` | `version_id` | 父 version | 条目 CRUD/导入 |
| `rag_traces` | `user_id` / dataset | 优先 `user_id`，否则父 dataset | Trace 查询 |
| `rag_evaluation_runs` | `user_id` / dataset/version | 优先 `user_id`，否则父 dataset | Run 列表/详情/取消/重试 |
| `rag_evaluation_results` | `run_id` | 父 Run | 结果分页/失败/钻取 |
| `rag_evaluation_failures` | **无表**（接口视图） | 随 `results` / Run | `/failures` 由 Run 租户过滤 |
| `audit_logs` | `user_id` nullable | `user_id` → 用户租户；NULL → 默认租户；**列保持 nullable** | 写入/查询（本期只写） |
| `llm_calls` | `user_id` nullable / datasource/task | 优先 user，其次 datasource/task，NULL → 默认租户；**列保持 nullable** | 成本查询/对账 |

### 3.3 本切片一起纳入的依赖表

- `knowledge_base` / `knowledge_gaps`：与 datasource 同级内容数据；若不纳入，知识接口会成为跨租户缺口。
- 其他用户级表（`user_llm_credentials`、`api_keys`、`webhooks`、`prompt_versions`、`prompt_usage_logs`、`version_rollback_logs`、`datasource_types`）**本期不加 tenant_id**，继续按 `user_id` 归属；列入后续切片。理由：不暴露跨用户数据、避免凭证/全局 Prompt 语义被租户切片拖大；风险与迁移窗口记录在 §10。

## 4. 迁移方案（023，仅设计）

### 4.1 升级步骤（单 migration，事务内）

1. 创建 `tenants`，插入默认租户。
2. 所有核心表新增 **nullable** `tenant_id` + FK `tenants(id)`（`ON DELETE RESTRICT`）。
3. 回填：
   - `users` → 默认租户；
   - 有 `user_id` 的表 → 用户租户；
   - 子表 → 父表 `tenant_id`；
   - `audit_logs` / `llm_calls` 的 NULL 用户 → 默认租户。
4. 校验：核心表 `tenant_id IS NULL` 计数必须为 0；子表与父表不一致计数必须为 0。
5. 业务表 `ALTER COLUMN tenant_id SET NOT NULL`；`audit_logs` / `llm_calls` 保持 nullable，允许平台级记录。
6. 建索引：`(tenant_id, created_at)`、`(tenant_id, user_id)`、子表 `(tenant_id, parent_id)`；按查询热点补。
7. `users.role` CHECK 扩展为 `platform_admin / tenant_admin / user / viewer`；存量 `admin` → `tenant_admin`。
8. 不在迁移里做存储对象搬迁；由代码双读 + 后续 backfill 脚本处理。

### 4.2 降级步骤

1. 恢复角色 CHECK；`tenant_admin` → `admin`，`platform_admin` → `admin`（降级语义写入文档）。
2. 删除新增索引/FK/列；删除默认租户（仅当无引用）。
3. 降级前要求 `TENANT_ENFORCEMENT_ENABLED=false`，避免代码仍按 tenant 查询。
4. 在 `aiinsight_test` 上执行 `upgrade head → downgrade -1 → upgrade head`，并跑迁移测试。

### 4.3 生产

- 本切片**不批准生产 migration**；先在 `aiinsight_test` + staging 验证。
- 生产窗口单独排期：备份、锁表评估、回填耗时、回滚脚本、监控。

## 5. 鉴权与角色

### 5.1 JWT

- access/refresh 增加 `tenant_id` claim；登录/刷新时从 `users.tenant_id` 生成。
- `get_current_user` 以 DB 用户为准，校验 claim 与 DB 一致；旧 token 无 `tenant_id` 时按 DB 用户租户解析（兼容一个发布周期，记录 warning）。
- 角色以 DB 为准，token 中 `role` 仅展示用途。

### 5.2 角色

| 角色 | 权限 |
|---|---|
| `platform_admin` | 跨租户运维；通过 `X-Tenant-Id` 选择目标租户；每次跨租户请求写 `audit_logs`；**仅 env/CLI 一次性引导，不自动建** |
| `tenant_admin` | 本租户管理员；本期只做成员/配置管理边界，**不默认获得其他用户业务数据**（见开放决策） |
| `user` | 本租户内自己的资源（沿用现有 user 归属） |
| `viewer` | 本租户只读 |

- 非 `platform_admin` 携带 `X-Tenant-Id`：忽略，不切换上下文。
- 跨租户资源按 ID 访问：统一 **404**（不返回 403，不泄露存在性）。
- `platform_admin` 跨租户写/读审计字段：`action='tenant.cross_access'`，`details` 含 `target_tenant_id`、method、path、resource_type、resource_id；不扩展完整审计能力。

### 5.3 TenantContext

新增依赖 `TenantContext`：
- `tenant_id`：普通用户 = 自己租户；platform_admin = header 指定或自己租户；
- `enforced`：`TENANT_ENFORCEMENT_ENABLED`；
- `actor_user_id` / `is_platform_admin`。

## 6. Repository / 服务强制

### 6.1 规则

- tenant-scoped 查询必须显式接收 `tenant_id`；禁止默认 `None` 绕过。
- 先按 `(tenant_id, id)` 查父资源；父资源不存在 → 404；再查子资源。
- 列表/分页/count 必须带 tenant 条件；不能只在详情加。
- 写入：子记录 `tenant_id` 从父资源继承，禁止从请求体接收。
- 后台任务：任务参数携带 `tenant_id`，或加载父记录后显式设置上下文；禁止 worker 使用“全局默认租户”隐式回退（除启动引导）。

### 6.2 覆盖矩阵

| 域 | 端点/服务 | 覆盖 |
|---|---|---|
| 数据源 | `/datasources` 列表/详情/更新/删除、上传、raw/cleaned | tenant + user |
| 质量/洞察 | `/analysis`、质量/洞察结果、盲区 | 经 datasource tenant |
| 知识 | `/knowledge` 列表/详情/导入/更新/删除 | 经 datasource tenant |
| 任务 | `/tasks` 列表/取消/重试/进度 | tenant + user |
| 报告 | `/datasources/{id}/reports`、`/reports/{id}`、download/delete | tenant + datasource |
| 数据集 | `/qa-datasets`、versions、items、publish/import | tenant + dataset |
| RAG Trace | `/rag/traces` | tenant + user/dataset |
| RAG 评测 | `/rag/evaluations`、results、failures、cancel/retry | tenant + run |
| 对比/报告 | 对比 Run、`run_comparison` 报告 | 两 Run 同 tenant；报告 tenant 一致 |
| 导出 | 前端 CSV/JSON（无后端接口） | 页面数据已 tenant 过滤；下载仅浏览器内 |
| 成本/看板 | `llm_calls` / cost 查询 | tenant + user |
| 后台任务 | digest / cost monitor / stale recovery / cleanup | 逐租户或平台任务显式标记 |

> **关键风险**：`digest` / `cost_monitor` 当前是全局聚合；多租户后：租户 UI/接口只返回当前 tenant，全局视图只允许 platform_admin 端点；后台任务按 tenant 分组，平台任务显式标 platform。验收会覆盖。

### 6.3 Tenant-scoped repository guard

- 不只靠每个查询手工加 `tenant_id`：提供 base/helper（列表、详情、count、下载、报告、对比、导出）统一注入 tenant 条件；
- 新增查询若没有 tenant 条件，测试/代码评审必须显式说明是平台任务；
- 跨租户统一 404，测试覆盖列表、详情、下载、报告、对比、导出。

## 7. 存储

### 7.1 Key 规范

| 类型 | 新 key |
|---|---|
| 上传/媒体 | `tenant/<tenant_id>/uploads/<datasource_id>/<uuid>_<filename>` |
| 报告 | `tenant/<tenant_id>/reports/<report_id>.<ext>` |

- `storage_service` 增加必填 `tenant_id`；禁止裸 `datasource_id`/`reports/` 新写入。
- 读取只能通过 DB 记录（raw/report）取得 key，不接受客户端传 object key。

### 7.2 历史对象兼容

1. 新写入一律新前缀；DB 记录保存新 key。
2. 旧记录保留旧 key；读取时 fallback 旧路径（`read_bytes` / `read_upload`）。
3. 可选 backfill：按租户复制对象到新 key，校验大小/checksum，更新 DB；旧对象保留一个观察期后再清理。
4. 本期不做批量搬迁；验收覆盖新旧 key 双读。

## 8. Feature flag / 灰度 / 回滚

| 项 | 设计 |
|---|---|
| Flag | `TENANT_ENFORCEMENT_ENABLED`，默认 **false** |
| false | 新数据仍写 `tenant_id` 与新存储前缀（双写）；查询保持现有 user 归属；单租户行为不变 |
| true | 所有 tenant-scoped 查询强制 `tenant_id`；跨租户 404；platform_admin 可用 header |
| 灰度 | `aiinsight_test` → staging(true) → 生产观察 → 生产(true) |
| 回滚 | flag=false；必要时 migration down（需代码回滚 + 对象兼容） |

## 9. 验收矩阵

### 9.1 迁移/回填

- `023` upgrade 后所有核心表 `tenant_id` 非空，存量数据 = 默认租户。
- 子表 tenant 与父表一致（Run/Result、Report/Datasource、Item/Version 等）。
- `upgrade head → downgrade -1 → upgrade head` 在 `aiinsight_test` 通过。
- 迁移测试在独立库执行，不依赖 dev 数据。

### 9.2 功能

| 用例 | 期望 |
|---|---|
| 同租户正常 | 列表/详情/上传/任务/报告/数据集/Trace/Run/结果/对比/导出全部正常 |
| 跨租户读 | 统一 404（不泄露存在性） |
| 跨租户写 | 父资源 404；不能把子记录写入他人租户 |
| 跨租户下载 | 报告/原始文件 404 |
| 跨租户报告/对比 | 两 Run 不同租户 → 404；报告生成拒绝 |
| 旧用户登录 | 自动落在默认租户，数据可见性不变 |
| platform_admin | header 切租户；每次跨租户操作写审计 |
| tenant_admin | 本租户边界；不越租户 |
| flag=false | 单租户行为与当前一致 |
| flag=true | 强制生效 |

### 9.3 回归

- 全量测试（`scripts/run_tests_local.py`）全绿，现有 1138 条不回退。
- 新增 tenant 测试覆盖同上矩阵。
- staging 冒烟：登录、上传、清洗、评测、对比、导出、报告下载。

## 10. 已确认决策（2026-11-25）

1. **email 全局唯一：保持。** 当前是“一个用户一个 tenant”；同一自然人跨 tenant 需后续 `tenant_memberships`，本期不做，不为未来提前拆唯一约束。
2. **tenant_admin 默认不看其他用户业务数据。** 只管理本租户用户/角色/设置、查看本租户聚合指标/账单；不默认读取他人对话/报告/Run 明细。后续需要时新增 `tenant_data_admin` 或显式 permission。
3. **platform_admin 仅 env/CLI 一次性引导。** 不自动建默认超级账号、不设默认密码；创建/变更写审计；现有 `admin` 映射为默认租户 `tenant_admin`，不是 platform_admin。
4. **凭证/API keys/prompt 表下一片再补。** 生产启用门禁：`TENANT_ENFORCEMENT_ENABLED=true` 上生产前，必须完成或证明 `user_llm_credentials`、`api_keys`、`webhooks`、prompt 系、`datasource_types` 已按 tenant 隔离。
5. **RLS 本期不做。** PR-1 先做 repository 显式 tenant 过滤、跨租户 404 测试、tenant-scoped guard、全量回归；RLS 作为后续 hardening slice。
6. **digest/cost：租户看租户，platform_admin 看全局。** 租户 UI/接口只返回当前 tenant；全局 digest/cost 只在 platform_admin 端点；后台任务按 tenant 分组，平台任务显式标 platform。
7. **历史存储对象：先双读，后批量搬迁。** 新写入 `tenant/<id>/...`；旧 key 双读；staging flag=true 稳定后单独 job，生产搬迁单独批准；访问必须校验 tenant/owner，不能只靠 key 前缀。

### 10.1 补充实现约束

- `audit_logs` / `llm_calls` 的 `tenant_id` 允许 NULL（平台级记录）；租户业务记录必须非空；平台级查询只允许 platform_admin。
- 引入 tenant-scoped repository guard（列表、详情、下载、报告、对比、导出），跨租户统一 404。
- 023 验收：默认租户幂等创建、回填幂等、upgrade/downgrade 在 `aiinsight_test` 连续两次、旧用户落默认租户、flag=false 单租户行为不变。

## 11. 建议 PR 拆分（批准后）

1. **PR-1**：`023` migration + `tenants` 模型 + `tenant_id` 字段/索引/回填 + 迁移测试（flag 默认 false，无行为变化）。
2. **PR-2**：JWT/角色/TenantContext + repository tenant 过滤 + 404 矩阵（flag 控制）。
3. **PR-3**：存储新前缀 + 历史双读 + 上传/报告接入。
4. **PR-4**：后台任务 tenant 化 + platform_admin 审计 + staging 验收。

> 每个 PR 独立可回滚；不把 audit/retention/alerting/cost/data-rights 混入。

## 12. 下一步

- 本 scope 审核通过后，才允许写 migration/代码。
- 先在 `aiinsight_test` 验证 migration up/down，再上 staging 开 flag。
- 生产 migration 与 flag 切换单独批准。

## 13. PR-1 批准范围（2026-11-25）

### 允许

- `023` migration：`tenants` + 默认租户 + `tenant_id` nullable/backfill/NOT NULL/index；
- 模型/关系更新（Tenant、tenant_id、必要索引）；
- 迁移测试、回填测试、up/down 连续两次测试；
- 仅在 `aiinsight_test` 执行。

### 不允许

- 生产 migration；
- JWT / Repository 改造提前混进 PR-1；
- 存储搬迁；
- audit / retention / alerting / cost 一起做；
- 打开 `TENANT_ENFORCEMENT_ENABLED=true`。

PR-2（JWT/Repo）等 PR-1 验收后再开。

## 14. PR-3 实施结果（2026-11-26，implemented / verified）

- 存储：上传 `tenant/<tenant_id>/uploads/<datasource_id>/...`；报告 `tenant/<tenant_id>/reports/...`；旧 key 继续可读。
- 025：移除 15 张业务表 `tenant_id` server_default，保留 NOT NULL / 外键；downgrade 恢复默认值仅用于回滚。
- 负向：flag=true 且无 TenantContext 时业务写入抛 `TENANT_CONTEXT_MISSING`；DB 层缺 tenant 插入被 NOT NULL 拒绝。
- 写入路径盘点：`docs/05-operations/04-m4a-pr3-write-paths.md`（API / Celery 子资源 / seed / 报告 / 数据集 / RAG）。
- 测试：`test_migration_025`、`test_tenant_enforcement`（含无 context 负向）、上传/报告 tenant 前缀、旧 key 下载；后端全量 **1163 passed / 255 deselected**。
- 冒烟：本地真实栈 `TENANT_ENFORCEMENT_ENABLED=true`：注册→建数据源→上传→清洗→报告→跨租户 404 全部通过；staging 待可访问环境执行同一 runbook。
- 边界：未做 retention/alerting/cost/RLS；未执行生产 migration；未在持久环境开启 flag。
