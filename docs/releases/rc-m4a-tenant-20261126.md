# RC1：m4a-tenant-20261126

> 状态：`release_candidate`（2026-11-26）
> 用途：M4-A tenant 切片的 staging 候选包；**不部署生产**
> 冻结：从本 RC 起只允许 P0 bugfix / 验收证据 / 发布文档；不允许新功能、PR-4 代码、M1 校准
> 下一道门：staging flag=true 冒烟（`05-m4a-staging-smoke-runbook.md`）

## 1. 包信息

| 项 | 内容 |
|---|---|
| RC 标识 | `rc-m4a-tenant-20261126` |
| 运行时提交 | `e2eaebd`（tenant storage / 025 / strict writes） |
| 测试与证据提交 | `deb9975`（旧 key 跨租户测试 + runbooks） |
| 后续提交 | `b2ef481` … `0a01b1b` 仅文档/scope，无运行时代码变化 |
| PR | #52 |
| 分支 | `feat/rag-phase3e-prompt-v11` |
| migration 链 | 023 `a7c4e9f2b6d1` → 024 `c1d5f8a3e7b2` → 025 `b8d3e6f1a2c9`（head） |
| 025 down_revision | `c1d5f8a3e7b2` |
| flag 默认 | `TENANT_ENFORCEMENT_ENABLED=false` |
| 部署范围 | 仅 staging / pre-prod 候选；生产 blocked |

## 2. 包含范围

- M4-A tenant 切片 PR-1 / 024 / PR-2 / PR-3（accepted for local/test）；
- tenants + 默认租户 + platform sentinel + 四角色；
- JWT tenant claim、TenantContext、Repository tenant guard、跨租户 404；
- 存储 tenant 前缀：`tenant/<tenant_id>/uploads/...`、`tenant/<tenant_id>/reports/...`；
- 旧 key 读取兼容；旧 key 跨租户授权测试；
- 025 移除 15 张业务表 `tenant_id` server_default；
- flag=true 无 context 负向写入失败；本地真实栈 flag=true 冒烟；
- 回滚 runbook、staging runbook、生产变更单模板。

## 3. 不包含 / 已知限制

| 项 | 状态 | owner / 优先级 |
|---|---|---|
| staging flag=true 冒烟 | 未执行；RC 的唯一边界门禁 | 项目 owner / P0 |
| 生产 migration | 未批准；变更单 draft | 项目 owner + 运维 / P0 |
| PR-4a 后台 context | scope 冻结；未实施（recover_stale 显式 context 待补） | 开发 / P2（staging 后） |
| PR-4b audit 扩展 | scope 冻结；未实施（outbox/append-only/before-after） | 开发 / P2（staging 后） |
| 旧对象批量搬迁 | 未做；仅读兼容 | 开发 / P2 |
| retention / alerting / cost / RLS | M4-A 不做 | 产品 / P2 |
| M1 v1.2.5 | beta / inactive；Judge 校准关闭 | M1 owner / known |
| `login.failure` / `token.revoke` 审计等级 | 暂低风险 best-effort；合规评审时复核 | 安全 / P3 |
| 前端 | 无新功能；沿用当前构建 | 前端 / known |

## 4. 发布就绪检查（2026-11-26）

| 项 | 结果 | 证据 |
|---|---|---|
| 后端全量 #1 | **1164 passed / 255 deselected**，295.89s | `rc_backend_run1.log` |
| 后端全量 #2 | **1164 passed / 255 deselected**，295.22s | `rc_backend_run2.log` |
| 连续两次 | 均全绿，无 flaky | 同上 |
| RC 定向门禁 | **45 passed**：023/024/025 migration、上传清洗、报告、storage、tenant enforcement | `rc_gate_targeted.log` |
| migration up/down | 025 up/down 两次；023/024 回填/角色测试通过 | `test_migration_023/024/025` |
| flag=false 单租户 | 上传/清洗/报告/数据源集成流程通过 | `test_upload_clean` / `test_reports_api` |
| flag=true 跨租户 | 数据源/任务/报告/数据集/Trace/Run 详情/下载/结果/失败 → 404；旧 key 跨租户 → 404 | `test_tenant_enforcement` |
| 旧 key 读取 | 旧上传 object_name / 旧报告 file_path 可读；tenant A 正常、B 404 | `test_storage` / `test_reports_api` / `test_tenant_enforcement` |
| 本地真实栈 | flag=true：注册→数据源→上传→清洗→报告→跨租户 404 通过；key 带 tenant 前缀 | 2026-11-26 smoke 记录 |
| 前端构建 | `npm run build` 成功（built in 35.34s） | `rc_frontend_build.log` |
| 静态检查 | black / flake8 / mypy / import-linter / alembic check 通过 | 本地输出 |
| CI | PR #52 全绿 | GitHub Actions |

### 本地真实栈冒烟摘要

| 项 | 值 |
|---|---|
| flag | true |
| user / datasource / raw / cleaned / report tenant | `00000000-0000-0000-0000-000000000001` |
| 上传 key | `tenant/000…001/uploads/<datasource>/<uuid>_smoke.csv` |
| 报告 file_path | `tenant/000…001/reports/<report>.md` |
| 清洗 | task completed；2 条 cleaned_data |
| 报告 | completed |
| 跨租户 | GET 他租户数据源 → 404 |
| 租户列表 | 只返回默认租户，不含其他租户 |

> 本地冒烟只证明代码路径，**不替代 staging 结论**。

## 5. 回滚

- 固定顺序：`06-m4a-rollback-runbook.md`；
- 先 `TENANT_ENFORCEMENT_ENABLED=false` + 重启 API/worker；
- 再 `alembic downgrade "$PRE_025_REV"`（当前链 `c1d5f8a3e7b2`）；
- 不清对象、不删 tenant；
- 目标 revision 演练时解析，不照抄旧值。

## 6. staging 时间盒

| 项 | 内容 |
|---|---|
| 开始 | 2026-11-27 |
| 截止 | **2026-12-01（3 个工作日）** |
| 输入 | 完整 `STAGING_SMOKE_INPUT` |
| 执行 | 按 `05-m4a-staging-smoke-runbook.md` |
| 回传 | head / 025 down_revision、0 NULL / 0 mismatch、Task/Run/Report ID、object key / file_path、跨租户 404、旧 key、回滚演练、耗时 |
| 到期未拿到输入 | 必须在下方 A/B/C 中决策，不允许无限等待 |

### 到期决策

| 选项 | 动作 | 结果 |
|---|---|---|
| A. VM pre-prod | 正式指定 VM 为 pre-prod；补备份/恢复/owner 签字；按同一 runbook 跑 | 可继续生产评审 |
| B. 内部演示版 | 发布 internal/demo；生产 migration 继续 blocked | 平台可用，租户生产不上 |
| C. 暂停 M4-A | 回到平台功能/体验；M4-A 保留 RC | 产品不被阻塞，租户化延期 |

推荐：VM 能隔离、能备份 → A；否则 B。禁止用本地/未指定环境冒充 staging。

## 7. 生产 Go/No-Go

生产 migration 只有全部满足才进入评审：

- staging flag=true 冒烟通过；
- 回滚演练通过（flag=false + 025 downgrade）；
- tenant 回填审计 0 NULL / 0 mismatch；
- 备份/恢复演练通过；
- 监控/告警窗口可观测；
- `07-m4a-prod-migration-change-ticket.md` 单独签字。

当前：**NO-GO / blocked**。

## 8. 线程关闭

| 线程 | 处理 |
|---|---|
| M1 Judge 校准 | 关闭；v1.2.5 beta / known issues |
| M2 P0 | accepted，关闭 |
| M3 P0 | accepted，关闭 |
| P1-0 ~ P1-5 | done，关闭 |
| M4-A scope 文档 | frozen，关闭追加 |
| PR-4 | 不批准，等 staging；scope frozen |
| staging | 唯一开放门禁 |
| 生产 migration | blocked，等 staging + 变更单 |

## 9. RC 规则

- 从本 RC 起不再改代码，除非 P0 bugfix；
- P0 bugfix 必须重跑 RC 门禁并重新打 tag；
- 新增范围走新 review，不往 frozen scope 追加；
- 本 RC 不部署生产，只作为 staging/pre-prod 候选。
