# 备份与恢复（ops/backup）

> 目标：让「备份能不能恢复」有一份**可重复执行、有明确 PASS/FAIL** 的答案，而不是一句运维口号。
> 首次落地：2026-11-11，VM `192.168.150.100` 实跑通过（见 §9）。

## 1. 覆盖范围

| 数据 | 方式 | 产物 |
| --- | --- | --- |
| PostgreSQL（业务 + `vector` 向量） | `pg_dump -Fc` + `sha256sum` | `$BACKUP_DIR/pg/aiinsight_<时间戳>.dump[.sha256]` |
| MinIO（上传原件、报告文件） | `mc mirror`（增量，**不带 `--remove`**） | `$BACKUP_DIR/minio/<bucket>/` |
| Redis | **不备份** | 可重建（限流计数、Celery 队列）；JWT 黑名单丢失只影响已登出 token 的提前失效时间 |
| `.env` / 加密密钥 | **不放进备份目录** | 必须离线另存，见 §6 |

默认 `BACKUP_DIR=/var/backups/ai-insight-hub`（在数据卷之外，不会被 `docker volume prune` 误删）。

## 2. 快速开始

```bash
# 全量（PG + MinIO）
sudo ./ops/backup/backup.sh

# 只备 PG（MinIO 为空时更快）
sudo ./ops/backup/backup.sh --no-minio

# 自定义目录与保留期
sudo BACKUP_DIR=/mnt/nas/aiih RETENTION_DAYS=14 ./ops/backup/backup.sh
```

输出示例（VM 实测，空库约 100KB）：

```
2026-11-11 16:32:27 [backup] 备份目录 /var/backups/ai-insight-hub 可用 27585MB
2026-11-11 16:32:27 [backup] pg_dump -Fc 开始：db=aiinsight user=aiinsight
2026-11-11 16:32:27 [backup] PG 备份完成：.../pg/aiinsight_20261111-163227.dump（108K）
2026-11-11 16:32:27 [backup] 保留策略 7 天：清理 0 个，剩余 4 → 4 个 dump
2026-11-11 16:32:28 [backup] mc mirror 开始：aiinsight-uploads → .../minio/aiinsight-uploads
2026-11-11 16:32:28 [backup] WARN bucket 不存在，跳过：aiinsight-reports
2026-11-11 16:32:28 [backup] WARN 未配置 OFFSITE_DIR：备份与业务数据在同一台机器/同一块盘，
2026-11-11 16:32:28 [backup] 全部完成，用时 1s
```

## 3. 定时任务

已安装在 VM（root crontab，`crond` active）：

```cron
# aiinsight-backup
10 3 * * * /root/ai-insight-hub/ops/backup/backup.sh >> /var/log/aiih-backup.log 2>&1
0 4 1 * * /root/ai-insight-hub/ops/backup/drill.sh > /var/log/aiih-backup-drill.log 2>&1
```

- 每日 03:10 备份；每月 1 日 04:00 自动演练一次；
- 安装/重建（幂等，重复执行不会写重复行）：

```bash
( crontab -l 2>/dev/null
  echo "# aiinsight-backup"
  echo "10 3 * * * /root/ai-insight-hub/ops/backup/backup.sh >> /var/log/aiih-backup.log 2>&1"
  echo "0 4 1 * * /root/ai-insight-hub/ops/backup/drill.sh > /var/log/aiih-backup-drill.log 2>&1"
) | crontab -
```

- 卸载：`crontab -l | grep -v aiinsight-backup | crontab -`（并手动删掉两行任务，见 README 的安装块）。

脚本失败会非零退出，cron 会按 `MAILTO` 发信；日志在 `/var/log/aiih-backup.log`。

## 4. 配置项

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `PROJECT_DIR` | 脚本上两级目录 | 仓库根（定位 `docker-compose.prod.yml`） |
| `COMPOSE_FILE` | `$PROJECT_DIR/docker-compose.prod.yml` | 部署编排文件 |
| `BACKUP_DIR` | `/var/backups/ai-insight-hub` | 备份根目录 |
| `RETENTION_DAYS` | `7` | dump 保留天数（MinIO 用镜像同步，不按天删） |
| `MIN_FREE_MB` | `1024` | 剩余空间低于该值直接拒绝备份 |
| `OFFSITE_DIR` | 空 | 离机副本目录（NAS 挂载点）；为空只告警 |
| `MINIO_BUCKETS` | `aiinsight-uploads aiinsight-reports` | 要镜像的桶（不存在的桶告警跳过） |
| `PG_SERVICE` / `MINIO_SERVICE` | `postgres` / `minio` | compose 服务名 |

数据库账号/库名、MinIO 账号**不在脚本里重复配置**，统一从运行中的容器环境变量读取（配置事实源仍是 `.env` + compose）。

## 5. 恢复

### 5.1 演练 / 抽查（不碰线上库）

```bash
# 默认还原到 <prod>_restore_<时间戳> 这种临时库
sudo ./ops/backup/restore.sh /var/backups/ai-insight-hub/pg/aiinsight_20261111-163227.dump

# 指定库名（已存在需 --drop）
sudo ./ops/backup/restore.sh <dump> --db aiinsight_restore_manual
```

### 5.2 真灾难恢复（覆盖线上库）

```bash
# 1) 先停写入，避免恢复过程中新数据被覆盖后回滚丢失
docker compose -f docker-compose.prod.yml stop api worker beat

# 2) 还原（必须显式确认，脚本默认拒绝写线上库）
sudo ALLOW_PROD_RESTORE=1 ./ops/backup/restore.sh <dump> --db aiinsight --drop --yes

# 3) 只回写对象存储（可选）
sudo ALLOW_PROD_RESTORE=1 ./ops/backup/restore.sh <dump> --db aiinsight --with-minio --yes

# 4) 起服务并验证
docker compose -f docker-compose.prod.yml start api worker beat
curl -fsS http://localhost/api/v1/health && docker compose -f docker-compose.prod.yml logs --tail=50 api
```

还原后脚本会自动打印 `tables / alembic_version / vector 扩展`，缺 `vector` 会告警（embedding 检索会失效）。

### 5.3 跨版本恢复

备份只含数据，不含代码版本。恢复后请确认 `alembic_version` 与当前代码一致；
若备份来自旧版本，先 `alembic upgrade head` 再起服务。

## 6. 必须单独保管的秘密（关键）

数据库里 `user_llm_credentials` 的 Key 是 **Fernet 加密**的，密钥是 `.env` 里的 `CREDENTIAL_ENCRYPTION_KEY`。
**丢了这把钥匙，恢复出来的库就是一堆无法解密的废数据。**

因此：

- `.env`（至少 `CREDENTIAL_ENCRYPTION_KEY` / `JWT_SECRET_KEY` / `MINIO_ROOT_PASSWORD` / `DEEPSEEK_API_KEY`）
  必须存进密码管理器或离线介质，**不要**和 dump 放在同一个目录；
- 换密钥会让历史凭据全部失效（用户需重新填写）。

## 7. 演练与验收

```bash
sudo ./ops/backup/drill.sh                 # 现场备份 → 还原 → 比对 → 清理
sudo ./ops/backup/drill.sh --no-backup     # 用最新历史备份
sudo ./ops/backup/drill.sh --keep          # 保留演练库，便于人工抽查
```

断言项（任一不过即 `FAIL` + 非零退出）：

1. `alembic_version` 与线上一致；
2. `vector` 扩展存在；
3. 表集合一致（多表/缺表都报错）；
4. **逐表 `count(*)` 一致**。

VM 实测（2026-11-11，18 张表）：

```
恢复演练 PASS：aiinsight_20261111-162832.dump → aiinsight_drill_20261111_163100（18 张表结构+行数全部一致）
```

负向验证（人为删表后再备份，确认断言不是空跑）：

```
WARN 断言失败：演练库缺表：webhooks
恢复演练 FAIL（2 项）
```

**建议频次**：每月一次（已挂 cron）；每次涉及迁移/表结构调整的发布后再手动跑一次。

## 8. 已知边界（明确不做的事）

| 项 | 说明 |
| --- | --- |
| 单机备份 ≠ 灾备 | 未配置 `OFFSITE_DIR` 时，备份与数据同盘；磁盘损坏/实例释放会一起丢。**生产必须配离机副本**（NAS / 对象存储 / 另一台机器） |
| MinIO 镜像不带 `--remove` | 线上误删的对象在备份里仍保留（便于找回），代价是备份只增不减，需要人工评估清理 |
| Redis 不备 | 设计上可重建；如需保留登出黑名单，另配 AOF + 卷备份 |
| 不含代码/镜像 | 恢复依赖同版本镜像；回滚代码请走镜像 tag |
| 演练库占额外空间 | 库大小 ≈ 线上库大小；当前 11MB 可忽略，数据到 GB 级时改为「每月人工 + 指定数据子集」 |

## 9. 首次落地记录（2026-11-11）

| 项 | 结果 |
| --- | --- |
| 环境 | VM `192.168.150.100`，`aiinsight-prod-*` 栈，PG 11MB / 18 表 / `alembic_version=c7d2e9b4a165` |
| 首次备份 | `aiinsight_20261111-163227.dump`（108K）+ sha256，MinIO `uploads` 56K |
| 恢复演练 | PASS，18 张表结构与行数全部一致 |
| 负向演练 | FAIL（缺表被识别），符合预期 |
| 防护测试 | 7/7：过期清理、未过期保留、拒绝写线上库、校验和不匹配、空间不足拒绝 |
| 定时任务 | 已写入 root crontab（每日 03:10 / 每月 1 日 04:00 演练） |
| 遗留 | **未配置 `OFFSITE_DIR`**（同机备份），需按 §8 补离机副本 |
