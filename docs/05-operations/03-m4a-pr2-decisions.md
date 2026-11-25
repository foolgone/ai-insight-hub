# M4-A PR-2 前置决策（tasks / server_default / 角色 / JWT / platform_admin）

> 状态：`decision_submitted`（2026-11-25）；**PR-2 代码未开始**
> 上游：`docs/05-operations/02-m4a-tenant-first-scope.md`（scope approved）
> PR-1：accepted（test/staging，仅 migration/模型）；生产 migration 未批准
> 本文只做决策，不写 migration/代码。

## 1. tasks 的平台任务语义

### 事实核对

- `tasks` 表当前只记录**用户/数据源业务任务**：clean、structure、evaluate、extract、analyze、report。
- `tasks.task_type` CHECK 不包含 digest / cost / stale recovery。
- `tasks.digest`、`tasks.cost_monitor`、`tasks.recover_stale_rag_runs` 只返回 Celery 结果，**不写 `tasks` 行**。
- 现有 `Task` 创建点均带 `user_id` / `datasource_id`；RAG Run、报告、数据集任务也都有用户归属。

### 决策：保持 `tasks.tenant_id NOT NULL`，平台任务使用 sentinel tenant

| 项 | 决定 |
|---|---|
| 当前语义 | `tasks` = 租户内用户业务任务；平台定时任务不落 `tasks` |
| 平台任务 | 若未来需要持久化 digest/cost/stale 等平台任务，使用固定 **platform sentinel tenant**（`slug='platform'`，固定 UUID），不把 `tenant_id` 改成 NULL |
| 024 migration | 预置 platform sentinel tenant（幂等），不扩 `task_type`；真正写入平台任务时再单独扩 type + 写任务 |
| 可见性 | platform sentinel 不出现在租户列表/租户页面；只允许 platform_admin 运维查询 |
| 备选（不采用） | `tasks.tenant_id NULL + CHECK`：会让所有 task 查询多一层 NULL 分支，且平台任务与租户任务混表 |

> 结论：**不需要把 tasks.tenant_id 改 NULL**；024 只补 platform sentinel，当前无平台任务行。

## 2. server_default 默认租户：PR-3 移除

### 风险

PR-1 给业务表 `tenant_id` 加了 `server_default = 默认租户`，保证 flag=false 时旧代码可写。但 flag=true 后，任何漏写 `tenant_id` 的写入路径会**静默落入默认租户**，这是跨租户污染风险。

### 决策

| 项 | 决定 |
|---|---|
| PR-2 | 保留 server_default；完成 JWT/Repo/TenantContext，flag 默认 false |
| PR-3 | 新增 migration（025）**删除业务表 server_default**；同步补“缺少 tenant context 时写入失败”的负向测试 |
| 开启 enforcement | 只在 PR-3 完成、负向测试通过后，staging 才允许 `TENANT_ENFORCEMENT_ENABLED=true` |
| 回滚 | flag=false + 代码回滚；恢复 server_default 需单独 migration，不默认回滚 |

> 不把“删默认值”混进 PR-2：JWT/Repo 改动已经很大，PR-2 保留默认值可降低部署/回滚耦合；PR-3 有明确的 hardening 关卡。

## 3. 旧 admin → 默认租户 tenant_admin

- PR-2 migration（024）把 `users.role` CHECK 扩展为 `platform_admin / tenant_admin / user / viewer`。
- 存量 `role='admin'` **全部映射为 tenant_admin**，归属默认租户。
- 迁移后不再允许新建 `admin`；测试/夹具中的 `role="admin"` 改为 `tenant_admin`。
- 旧 JWT 的 `role` claim 不用于鉴权（`require_roles` 以 DB 用户角色为准），因此旧 token 不会因 claim 仍是 admin 被误判；DB 映射后立即按 tenant_admin 生效。
- 旧 `admin` 不自动升为 platform_admin。

## 4. 旧 JWT 无 tenant_id 的兼容周期

| 项 | 决定 |
|---|---|
| access token | 60 分钟；旧 token 无 `tenant_id` 时，从 DB `users.tenant_id` 解析（默认租户），记录一次 warning |
| refresh token | 7 天；刷新时按 DB 用户租户签发新 claim，完成自然轮换 |
| claim 与 DB 不一致 | 以 DB 为准；不一致视为异常 → 401，要求重新登录（防止伪造/漂移） |
| 兼容期 | 一个 refresh 周期（7 天）；兼容期结束后，无 `tenant_id` 的 access token 直接拒绝 |
| 测试 | 旧 token（无 claim）可完成一个请求并落默认租户；refresh 后新 token 带 claim；伪造 mismatch → 401 |

## 5. platform_admin 引导与审计

| 项 | 决定 |
|---|---|
| 创建方式 | **一次性 CLI**（`scripts/create_platform_admin.py`）或显式 `PLATFORM_ADMIN_EMAILS` 引导；不自动建、不设默认密码 |
| 现有 admin | 只映射 tenant_admin；不自动成为 platform_admin |
| 切租户 | `X-Tenant-Id`；仅 platform_admin 可用，其他角色忽略 |
| 审计 | 每次跨租户请求写 `audit_logs`：`action='tenant.cross_access'`，`details` 含 target_tenant_id、method、path、resource_type、resource_id、actor |
| 查询 | 本期只写审计；不做审计查询界面/不可篡改 |
| 测试 | platform_admin 切租户成功且产生审计；普通用户带 header 不切租户；跨租户资源仍 404 |

## 6. PR-2 执行顺序（决策通过后）

1. **024 migration**：platform sentinel tenant + 角色 CHECK 扩展 + admin→tenant_admin（独立 migration，不混代码）。
2. JWT：`tenant_id` claim、旧 token 兼容、刷新轮换。
3. TenantContext：普通用户本租户；platform_admin header 切换。
4. Repository guard：tenant-scoped base/helper，覆盖列表/详情/下载/报告/对比/导出。
5. 跨租户 404 测试 + flag=false 回归。
6. PR-2 不开启 staging flag；等 PR-3 删除 server_default 后再开。

## 7. PR-2 明确不做

- 存储前缀/批量搬迁（PR-3）。
- retention / alerting / cost 预算 / data-rights / RLS。
- 生产 migration；不打开 `TENANT_ENFORCEMENT_ENABLED=true`。
- 不改 M1 / Judge / target / Prompt。
