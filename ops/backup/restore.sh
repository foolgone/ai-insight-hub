#!/usr/bin/env bash
# 恢复：把一个 pg_dump -Fc 备份还原到指定库（默认还原到「新建的临时库」，不会动线上库）
#
# 用法：
#   ./ops/backup/restore.sh /var/backups/ai-insight-hub/pg/aiinsight_20261111-031000.dump
#   ./ops/backup/restore.sh <dump> --db aiinsight --yes          # 覆盖线上库（需 ALLOW_PROD_RESTORE=1）
#   ./ops/backup/restore.sh <dump> --db aiinsight_restore_x --with-minio --yes
#
# 安全默认：
# - 目标库名默认是 <prod>_restore_<时间戳>，避免手滑覆盖线上；
# - 还原到线上库（POSTGRES_DB）需要显式 ALLOW_PROD_RESTORE=1 + --yes；
# - 覆盖已有目标库需要 --drop。
set -euo pipefail
source "$(cd -- "$(dirname -- "$0")" && pwd)/common.sh"

DUMP=""
TARGET_DB=""
ASSUME_YES=0
DROP_EXISTING=0
WITH_MINIO=0

while [ $# -gt 0 ]; do
  case "$1" in
    --db) TARGET_DB="$2"; shift 2 ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --drop) DROP_EXISTING=1; shift ;;
    --with-minio) WITH_MINIO=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    -*) die "未知参数：$1（-h 查看用法）" ;;
    *) DUMP="$1"; shift ;;
  esac
done

[ -n "$DUMP" ] || die "缺少备份文件参数（-h 查看用法）"
[ -f "$DUMP" ] || die "备份文件不存在：$DUMP"

require_stack
verify_checksum "$DUMP"

PROD_DB="$(pg_db)"
DB_USER="$(pg_user)"
TARGET_DB="${TARGET_DB:-${PROD_DB}_restore_$(date +%Y%m%d_%H%M%S)}"
printf '%s' "$TARGET_DB" | grep -Eq '^[a-z0-9_]+$' \
  || die "目标库名只允许小写字母/数字/下划线：$TARGET_DB"

if [ "$TARGET_DB" = "$PROD_DB" ] && [ "${ALLOW_PROD_RESTORE:-0}" != "1" ]; then
  die "拒绝还原到线上库 $PROD_DB：确认要覆盖请加 ALLOW_PROD_RESTORE=1 并先停掉 api/worker"
fi

db_exists() {
  [ "$(psql_db postgres "select 1 from pg_database where datname = '$TARGET_DB'")" = "1" ]
}

if db_exists; then
  if [ "$DROP_EXISTING" != 1 ]; then
    die "目标库 $TARGET_DB 已存在；覆盖请加 --drop（原库会先被删除）"
  fi
  if [ "$ASSUME_YES" != 1 ]; then
    read -r -p "将删除并重建数据库 $TARGET_DB，确认？[y/N] " answer
    [ "$answer" = "y" ] || die "已取消"
  fi
  log "删除已有库 $TARGET_DB"
  psql_db postgres "drop database if exists \"$TARGET_DB\" with (force)" >/dev/null
fi

log "创建目标库 $TARGET_DB（owner=$DB_USER）"
psql_db postgres "create database \"$TARGET_DB\"" >/dev/null

log "pg_restore 开始：$DUMP → $TARGET_DB"
if ! compose exec -T "$PG_SERVICE" \
    pg_restore -U "$DB_USER" -d "$TARGET_DB" --no-owner --no-privileges --exit-on-error \
    < "$DUMP"; then
  die "pg_restore 失败（目标库 $TARGET_DB 保留现场，便于排查）"
fi

HEAD="$(psql_db "$TARGET_DB" "select version_num from alembic_version" 2>/dev/null || true)"
TABLES="$(psql_db "$TARGET_DB" "select count(*) from pg_tables where schemaname='public'")"
EXT_VECTOR="$(psql_db "$TARGET_DB" "select count(*) from pg_extension where extname='vector'")"

log "还原完成：tables=$TABLES alembic_version=${HEAD:-<空>} vector_ext=$EXT_VECTOR"
[ "$EXT_VECTOR" = "1" ] || warn "目标库缺少 vector 扩展，embedding 相关查询会失败"

if [ "$WITH_MINIO" = 1 ]; then
  [ "$ASSUME_YES" = 1 ] || die "--with-minio 需要同时加 --yes（会把备份对象写回线上桶）"
  MINIO_USER_="$(container_env "$MINIO_SERVICE" MINIO_ROOT_USER minioadmin)"
  MINIO_PASS_="$(container_env "$MINIO_SERVICE" MINIO_ROOT_PASSWORD "")"
  [ -n "$MINIO_PASS_" ] || die "读取不到 MINIO_ROOT_PASSWORD"
  NET="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' \
    "$(compose ps -q "$MINIO_SERVICE")")"
  for bucket in $MINIO_BUCKETS; do
    [ -d "$BACKUP_DIR/minio/$bucket" ] || { warn "备份里没有 $bucket，跳过"; continue; }
    log "mc mirror 回写：$BACKUP_DIR/minio/$bucket → $bucket"
    docker run --rm --network "$NET" \
      -e "MC_HOST_local=http://${MINIO_USER_}:${MINIO_PASS_}@${MINIO_SERVICE}:9000" \
      -v "$BACKUP_DIR/minio:/backup" \
      minio/mc:latest mirror --overwrite "/backup/${bucket}" "local/${bucket}" >/dev/null \
      || die "MinIO 回写失败：$bucket"
  done
fi

cat <<EOF

恢复完成。
  目标库：$TARGET_DB
  连接串：postgresql://$DB_USER:***@<host>:5432/$TARGET_DB
  抽查：docker compose -f $COMPOSE_FILE exec -T $PG_SERVICE \\
        psql -U $DB_USER -d $TARGET_DB -c '\\dt'
  用完清理：docker compose -f $COMPOSE_FILE exec -T $PG_SERVICE \\
        psql -U $DB_USER -d postgres -c 'drop database if exists "$TARGET_DB" with (force)'
EOF
