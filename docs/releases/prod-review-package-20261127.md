# 生产 migration 评审包（开发侧提交，draft / NO-GO）

> 提交角色：开发
> 状态：`deferred_by_product_priority`（2026-11-27）；**不是生产批准，也不再补证**
> 变更单：`docs/05-operations/07-m4a-prod-migration-change-ticket.md`
> Pre-prod 证据：`docs/releases/preprod-acceptance-20261127.md`（accepted）
> RC：`rc-m4a-tenant-20261126` / 提交 `51d6619` / 运行时 `e2eaebd`
> 结论：**DEFERRED**。产品优先，生产多租户暂缓；六项运维证据停止收集，生产 migration 不排期。

## 1. 变更摘要

| 项 | 内容 |
|---|---|
| 迁移 | 023 → 024 → 025，head `b8d3e6f1a2c9`，025 down `c1d5f8a3e7b2` |
| flag | `TENANT_ENFORCEMENT_ENABLED=false` 默认；生产开 flag 另行审批 |
| 回滚 | `06-m4a-rollback-runbook.md`；先 flag=false，再 downgrade 025 |
| 部署方式 | 单独生产变更单；不随 RC tag 自动执行 |
| 当前生产 | 未碰、未迁移、未激活 |

## 2. 六项门禁

| # | 项 | 状态 | 证据 / 待补 | Owner |
|---|---|---|---|---|
| 1 | MinIO/S3 IAM、bucket policy、tenant 前缀、旧 key | **未完成** | storage smoke 或书面风险接受 | 运维 + owner |
| 2 | 生产 nginx / TLS / 上传大小 / 超时 | **未完成** | nginx -t、证书、100MB/120m、proxy timeout | 运维 |
| 3 | 生产备份/恢复 + 025 downgrade 演练 | **未完成** | 备份负责人/路径、恢复演练、回滚窗口 | DBA/运维 |
| 4 | 生产 tenant 回填审计 + 迁移前快照 | **待执行** | SQL 已备（见 07）；迁移窗口执行并记录 0/0 | 开发 + DBA |
| 5 | 监控/告警 | **未确认** | API/worker/DB/Redis/对象存储告警 | 运维 |
| 6 | owner + 运维/DBA 签字 | **未签** | 维护窗口、回滚触发条件、签字表 | owner/运维/DBA |

## 3. 开发侧已完成

| 项 | 证据 |
|---|---|
| RC 冻结 | tag `rc-m4a-tenant-20261126`，提交 `51d6619` |
| Pre-prod accepted | 023–025、tenant 隔离、旧 key、025 回滚；见 `preprod-acceptance-20261127.md` |
| 迁移链 | 023 `a7c4e9f2b6d1` → 024 `c1d5f8a3e7b2` → 025 `b8d3e6f1a2c9` |
| 回滚 runbook | `06-m4a-rollback-runbook.md`，pre-prod 演练 2.6s downgrade / 2.5s re-upgrade |
| 回填审计 SQL | `07` §2.1，15 表 NULL + 8 组父子一致性 |
| 变更单模板 | `07`，含维护窗口、监控、回滚、签字 |
| 运行时代码 | 冻结；仅 P0 bugfix 可动，且需重跑 RC 门禁/重打 tag |

## 4. 待运维/DBA 提供

### 4.1 Storage smoke（或书面风险接受）

- 环境：staging/pre-prod MinIO，或生产同构 bucket；**不使用真实客户数据**。
- 检查项：
  1. IAM：仅目标 bucket/prefix 的最小权限；无 admin；
  2. bucket policy：私有、TLS、禁止公开 list；
  3. 上传：`tenant/<id>/uploads/...` 写入/读取；
  4. 报告：`tenant/<id>/reports/...` 写入/下载；
  5. 旧 key：旧 `object_name` / `file_path` 可读；
  6. 跨租户：B 访问 A 的对象/报告 → 404；
  7. 清理测试对象并记录 bucket / prefix / key / 操作人 / 时间。
- 若选择风险接受：必须由 owner 书面写明未验证范围、补偿控制、批准人和有效期；不得口头默认。

### 4.2 Nginx / TLS

- `nginx -t` 通过；证书链/到期时间；TLS 配置；
- 上传 100MB 与 `client_max_body_size 120m` 对齐；
- `proxy_read_timeout 120s`、`/api` 反代、SSE/WS（如适用）；
- 只在维护窗口内改配置，改后重启并 smoke。

### 4.3 生产备份/恢复

- 备份负责人、路径、权限（600）；
- `pg_dump` + 恢复演练到临时库/环境，确认 pgvector/extension；
- 025 downgrade 演练（生产同构副本或维护窗口），验证 15 表 default 恢复；
- 回滚截止时间与触发条件。

### 4.4 生产 tenant 审计

- 迁移前对生产快照/只读副本执行 `07` §2.1；
- 15 表 0 NULL；8 组父子 0 mismatch；
- 记录快照时间、revision、执行人、SQL 输出。

### 4.5 监控/告警

- API 5xx、延迟；worker 失败率/队列深度；DB 连接/锁；Redis；
- 对象存储错误；迁移窗口内告警接收人与升级路径。

### 4.6 签字

- owner + 运维/DBA；维护窗口、回滚触发条件、生产 migration 单独批准。

## 5. Go/No-Go

**当前：DEFERRED by product priority。**

不是技术 NO-GO，而是产品决策暂缓；恢复时需重新提交评审包并补六项证据。

- 1/2/3/5/6 未完成；4 需迁移窗口执行；
- 只有六项齐全并签字后，才可排生产维护窗口；
- 生产 migration 不跟随 RC tag 自动执行；
- Pre-prod accepted 不等于 production ready，尤其不覆盖 MinIO/S3 与 nginx/TLS。

## 6. 恢复条件（非当前行动）

只有产品决定恢复多租户生产时，才重新启动以下步骤：

1. 运维提供 1/2/5 证据或风险接受；
2. DBA/运维提供 3 的演练记录与窗口；
3. 开发在窗口执行 4 的只读审计并回传 0/0；
4. owner + 运维/DBA 签字 6；
5. 另开生产 migration 批准，不自动执行。

> 本评审包由开发提交；完整性审查、风险接受和 go/no-go 由决策/owner 角色完成。

## 7. 产品优先决策（2026-11-27）

- 生产多租户 migration：`deferred_by_product_priority`；
- 停止：生产评审包补证、生产 migration/变更单、PR-4 代码、M4-A tenant 生产化、M1 校准；
- 继续：产品演示与体验、M2/M3 工作台、preprod 真实 Run、产品功能补齐、客户反馈；
- 生产保持：未碰、未迁移、未激活；RC1 frozen；
- 恢复多租户生产时，本评审包需重新做完整性审查，不自动沿用。
