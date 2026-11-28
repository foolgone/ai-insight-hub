# Pre-prod 验收记录：VM pre-prod（2026-11-27）

> 状态：`accepted`（2026-11-27，owner 追认）
> RC：`rc-m4a-tenant-20261126`（tag `51d6619`，运行时 `e2eaebd`）
> 结论：pre-prod accepted；**不等于 production ready**
> 生产 migration：仍 `blocked`，进入变更单评审，不自动批准

## 1. 窗口与偏差

| 项 | 记录 |
|---|---|
| 原批准窗口 | 2026-11-27 10:00–12:00 Asia/Shanghai |
| 实际执行 | 2026-11-27 00:22–00:40 Asia/Shanghai |
| 偏差 | 早于 10:00 窗口执行；owner 追认为等效批准窗口 |
| 处理 | 记录一次，不重跑；后续窗口按新批准执行 |

## 2. 范围

| 覆盖 | 不覆盖 |
|---|---|
| 023–025 在 022 数据上迁移 | MinIO/S3 IAM、bucket policy、网络 |
| tenant 回填 0 NULL / 0 mismatch | 生产 nginx / TLS |
| 新 key 前缀 / 旧 key 读取 | 生产负载 / 并发 |
| tenant 隔离 / B 404 | 生产备份/恢复窗口 |
| platform_admin 跨租户 + 审计 | 生产 migration |
| 025 downgrade / re-upgrade | 真实客户数据 |

## 3. 环境

| 项 | 值 |
|---|---|
| App | Windows 宿主机 API / worker / Vite |
| DB | VM `aiinsight-postgres`（5433），database `aiinsight_preprod` |
| Redis | DB 3 app / 4 broker / 5 result |
| Storage | `backend/.storage/preprod`，local |
| RAG | `RAG_ADAPTER=mock` |
| 初始 flag | false；中途 true；最终 false |
| 源数据 | dev `aiinsight` dump（022，测试数据）；dev 库未写 |

## 4. 迁移与审计

| 项 | 结果 |
|---|---|
| 迁移前 revision | `f3a9c2d7e1b4`（022） |
| 迁移后 head | `b8d3e6f1a2c9`（025） |
| 025 down_revision | `c1d5f8a3e7b2` |
| 升级耗时 | 10.3s（含 current/upgrade/current） |
| tenant 回填 | 15 表 0 NULL；父子 0 mismatch |
| 025 默认值 | 15 表 `column_default` 为 NULL |
| 回滚前备份 | `/root/aiinsight_preprod_backups/aiinsight_preprod_before_rollback_20261127_0027.dump`（600） |
| 023 前备份 | `/root/aiinsight_preprod_backups/aiinsight_preprod_before_023_20261127_0017.dump`（600） |
| dev dump | `/root/aiinsight_preprod_backups/aiinsight_dev_20261127_0017.dump`（600） |
| 恢复演练 | `aiinsight_preprod_restore`，rev 022，24 users，pgvector 0.8.7 |

## 5. 功能证据

| 项 | 值 |
|---|---|
| flag=false 数据源 | `282ff05c-2f22-4c62-86f4-d80f0a41a53e` |
| flag=false Task | `dff3bf40-b75e-4c93-8a55-356aae0aaa64` completed |
| flag=false Report | `354a10cc-6d2d-4edf-bc1a-f4db6916462a` completed |
| flag=true 数据源 | `9c898f61-4aa0-477d-8139-69578d8533c0` |
| flag=true Task | `c58f90a4-94ac-44d2-8d4f-04462009d444` completed |
| flag=true Report | `3d747fc5-41f4-44c5-9d6c-88e75b1fa543` completed |
| 上传 key | `tenant/1111…/uploads/<datasource>/…` |
| 报告 file_path | `tenant/1111…/reports/<report>.md` |
| 旧 key Report | `97689639-7656-44b4-9deb-f072d9324a2b`，`reports/legacy-preprod-…md`；A 下载 200 |
| B 跨租户 | 数据源 / 报告 / 下载 / 旧 key 下载 → 404 |
| platform_admin | X-Tenant-Id=A → 200；`tenant.cross_access` audit id 984，target=A |
| 租户列表 | A 仅返回 A；不含 sentinel / B |

## 6. 回滚

| 步骤 | 结果 |
|---|---|
| flag=false + 重启 | 通过 |
| 回滚前单租户冒烟 | ds `5f4764b5…`，Task `bcf05fcf…` completed |
| downgrade 025→024 | 2.6s；revision `c1d5f8a3e7b2` |
| 15 表默认值 | 全部恢复为默认租户 |
| 回滚后单租户冒烟 | ds `92ae3292…`，Task `43ea02ac…` completed |
| re-upgrade | 2.5s；head 025；0 NULL / 0 mismatch；default NULL |
| 最终 flag | false；B 访问 A → 403（ownership） |

## 7. 收尾

- 测试账号密码文件已删除/不可恢复：`preprod_credentials.json`（本地临时目录）。
- `aiinsight_preprod`、`aiinsight_preprod_restore`、备份文件保留为证据；不再用于新测试，避免证据漂移。
- 本机 API / worker / Vite 已停止，8000/5173 已释放。
- `aiinsight` dev 库未写入，revision 仍 022。

## 8. 生产评审前仍需

| 项 | 状态 |
|---|---|
| MinIO/S3 storage smoke，或书面接受未验证风险 | 待办 |
| 生产 nginx / TLS / 上传大小 / 超时 | 待办 |
| 生产备份/恢复演练 + 025 downgrade 演练 | 待办 |
| 生产 tenant 回填审计 0 NULL / 0 mismatch + 迁移前快照 | 待办 |
| 监控/告警窗口可观测 | 待办 |
| `07-m4a-prod-migration-change-ticket.md` owner + 运维/DBA 签字 | 待办 |

> Pre-prod accepted 只证明 VM pre-prod 的迁移/租户/旧 key/回滚；生产 migration 仍单独评审、单独批准，不随 RC tag 自动执行。
