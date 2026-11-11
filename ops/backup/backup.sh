#!/usr/bin/env bash
# 备份：PostgreSQL（pg_dump -Fc）+ MinIO 对象（mc mirror）+ sha256 + 保留期清理 + 可选离机副本
#
# 用法：
#   ./ops/backup/backup.sh                 # PG + MinIO
#   ./ops/backup/backup.sh --no-minio      # 只备 PG（MinIO 为空时更快）
#   BACKUP_DIR=/mnt/nas/aiih ./ops/backup/backup.sh
#
# 退出码：0 成功；非 0 失败（cron 会把 stderr 发给 MAILTO）
set -euo pipefail
source "$(cd -- "$(dirname -- "$0")" && pwd)/common.sh"

DO_PG=1
DO_MINIO=1

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) BACKUP_DIR="$2"; shift 2 ;;
    --no-pg) DO_PG=0; shift ;;
    --no-minio) DO_MINIO=0; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) die "未知参数：$1（-h 查看用法）" ;;
  esac
done

START_TS=$(date +%s)
STAMP="$(date +%Y%m%d-%H%M%S)"
DUMP=""

prune_pg() {
  local dir="$BACKUP_DIR/pg" before after deleted
  before=$(find "$dir" -maxdepth 1 -name '*.dump' | wc -l)
  deleted=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    rm -f -- "$f" "$f.sha256"
    deleted=$((deleted + 1))
  done < <(find "$dir" -maxdepth 1 -type f -name '*.dump' -mtime "+$RETENTION_DAYS")
  after=$(find "$dir" -maxdepth 1 -name '*.dump' | wc -l)
  log "保留策略 ${RETENTION_DAYS} 天：清理 ${deleted} 个，剩余 ${before} → ${after} 个 dump"
  [ "$after" -ge 1 ] || die "清理后没有任何 dump 文件，保留策略过于激进（RETENTION_DAYS=$RETENTION_DAYS）"
}

backup_pg() {
  local user db size
  user="$(pg_user)"
  db="$(pg_db)"
  DUMP="$BACKUP_DIR/pg/${db}_${STAMP}.dump"

  log "pg_dump -Fc 开始：db=$db user=$user"
  if ! compose exec -T "$PG_SERVICE" pg_dump -U "$user" -d "$db" -Fc > "$DUMP"; then
    rm -f -- "$DUMP"
    die "pg_dump 失败（容器 $PG_SERVICE，db=$db）"
  fi

  # custom 格式的魔数，防止「命令成功但文件写了一半」
  [ "$(head -c 5 "$DUMP")" = "PGDMP" ] || { rm -f -- "$DUMP"; die "dump 文件头非法：$DUMP"; }

  ( cd "$BACKUP_DIR/pg" && sha256sum "$(basename -- "$DUMP")" > "$(basename -- "$DUMP").sha256" )
  size="$(du -h "$DUMP" | cut -f1)"
  log "PG 备份完成：$DUMP（$size）"
}

backup_minio() {
  local user pass net bucket
  user="$(container_env "$MINIO_SERVICE" MINIO_ROOT_USER minioadmin)"
  pass="$(container_env "$MINIO_SERVICE" MINIO_ROOT_PASSWORD "")"
  [ -n "$pass" ] || die "读取不到 MINIO_ROOT_PASSWORD（容器 $MINIO_SERVICE 是否在运行？）"

  net="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' \
    "$(compose ps -q "$MINIO_SERVICE")")"
  [ -n "$net" ] || die "无法解析 $MINIO_SERVICE 所在 docker 网络"

  for bucket in $MINIO_BUCKETS; do
    log "mc mirror 开始：$bucket → $BACKUP_DIR/minio/$bucket"
    # 不加 --remove：线上误删的对象仍保留在备份里，便于找回
    # 直接给 mc 传参（mc 镜像是 entrypoint=mc 的精简镜像，不能 sh -c）
    if ! mc_out="$(docker run --rm --network "$net" \
        -e "MC_HOST_local=http://${user}:${pass}@${MINIO_SERVICE}:9000" \
        -v "$BACKUP_DIR/minio:/backup" \
        minio/mc:latest mirror --overwrite "local/${bucket}" "/backup/${bucket}" 2>&1)"; then
      if printf '%s' "$mc_out" | grep -q 'does not exist'; then
        # 桶还没被创建（例如从未生成过报告）不是故障
        warn "bucket 不存在，跳过：$bucket"
        continue
      fi
      printf '%s\n' "$mc_out" >&2
      die "mc mirror 失败：bucket=$bucket"
    fi
  done
  log "MinIO 备份完成：$(du -sh "$BACKUP_DIR/minio" | cut -f1)"
}

copy_offsite() {
  [ -n "$OFFSITE_DIR" ] || { warn_if_not_offsite; return 0; }
  mkdir -p "$OFFSITE_DIR/pg" "$OFFSITE_DIR/minio"
  if [ -n "$DUMP" ]; then
    cp -f -- "$DUMP" "$DUMP.sha256" "$OFFSITE_DIR/pg/"
  fi
  if [ "$DO_MINIO" = 1 ]; then
    cp -a -- "$BACKUP_DIR/minio/." "$OFFSITE_DIR/minio/"
  fi
  log "离机副本完成：$OFFSITE_DIR"
}

check_free_space
lock_or_die
mkdir -p "$BACKUP_DIR/pg" "$BACKUP_DIR/minio"

if [ "$DO_PG" = 1 ]; then
  require_stack
  backup_pg
  prune_pg
fi

if [ "$DO_MINIO" = 1 ]; then
  require_stack
  backup_minio
fi

copy_offsite

log "全部完成，用时 $(( $(date +%s) - START_TS ))s"
