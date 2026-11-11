#!/usr/bin/env bash
# AI Insight Hub 备份/恢复共用逻辑（被 backup.sh / restore.sh / drill.sh source）
#
# 设计原则：
# - 配置只有一份事实源：容器内的 POSTGRES_* / MINIO_ROOT_*，脚本不重复写一遍；
# - 所有 docker 调用都走 `docker compose -f $COMPOSE_FILE`，与部署方式一致；
# - 失败必须非零退出，交给 cron/告警发现，不允许「半成功」。
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd -- "$SCRIPT_DIR/../.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-$PROJECT_DIR/docker-compose.prod.yml}"

# 备份根目录：默认放在仓库与数据卷之外，避免被 docker volume prune 误删
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ai-insight-hub}"
# PG dump 保留天数（MinIO 用镜像同步，不按天删，见 README）
RETENTION_DAYS="${RETENTION_DAYS:-7}"
# 剩余空间低于该值直接拒绝备份，避免写满磁盘把线上拖挂
MIN_FREE_MB="${MIN_FREE_MB:-1024}"
# 离机副本目录（NAS 挂载点 / rclone 同步目录）；为空则只报警告
OFFSITE_DIR="${OFFSITE_DIR:-}"

PG_SERVICE="${PG_SERVICE:-postgres}"
MINIO_SERVICE="${MINIO_SERVICE:-minio}"
MINIO_BUCKETS="${MINIO_BUCKETS:-aiinsight-uploads aiinsight-reports}"

_log_tag() { basename -- "${0%%.sh}"; }
ts() { date '+%F %T'; }
log() { printf '%s [%s] %s\n' "$(ts)" "$(_log_tag)" "$*"; }
warn() { printf '%s [%s] WARN %s\n' "$(ts)" "$(_log_tag)" "$*" >&2; }
die() {
  printf '%s [%s] ERROR %s\n' "$(ts)" "$(_log_tag)" "$*" >&2
  exit 1
}

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

require_stack() {
  command -v docker >/dev/null 2>&1 || die "未找到 docker 命令"
  [ -f "$COMPOSE_FILE" ] || die "未找到 compose 文件：$COMPOSE_FILE（可用 COMPOSE_FILE 指定）"
  [ -n "$(compose ps -q "$PG_SERVICE" 2>/dev/null || true)" ] \
    || die "$PG_SERVICE 容器未运行（COMPOSE_FILE=$COMPOSE_FILE）"
}

# 读取容器内环境变量：配置事实源在 compose/.env，脚本不自带副本
# < /dev/null 必须保留：docker exec 会吞掉调用方（如 while read 循环）的 stdin
container_env() {
  local svc="$1" key="$2" default="${3:-}" value
  value="$(compose exec -T "$svc" sh -c "printf %s \"\${$key:-}\"" < /dev/null 2>/dev/null || true)"
  if [ -n "$value" ]; then printf '%s' "$value"; else printf '%s' "$default"; fi
}

pg_user() { container_env "$PG_SERVICE" POSTGRES_USER aiinsight; }
pg_db() { container_env "$PG_SERVICE" POSTGRES_DB aiinsight; }

# psql_db <db> <sql>
# < /dev/null 必须保留：否则 docker exec 会吞掉调用方（如 while read 循环）的 stdin
psql_db() {
  local db="$1"
  shift
  compose exec -T "$PG_SERVICE" psql -v ON_ERROR_STOP=1 -U "$(pg_user)" -d "$db" -tAc "$*" \
    < /dev/null
}

check_free_space() {
  mkdir -p "$BACKUP_DIR"
  local avail
  avail="$(df -Pm "$BACKUP_DIR" | awk 'NR==2 {print $4}')"
  [ "${avail:-0}" -ge "$MIN_FREE_MB" ] \
    || die "备份目录剩余空间不足：${avail:-0}MB < ${MIN_FREE_MB}MB（$BACKUP_DIR）"
  log "备份目录 $BACKUP_DIR 可用 ${avail}MB"
}

# 防止 cron 重入（上一次还没跑完就又触发）
lock_or_die() {
  mkdir -p "$BACKUP_DIR"
  LOCK_FILE="$BACKUP_DIR/.backup.lock"
  exec 9>"$LOCK_FILE" || die "无法创建锁文件 $LOCK_FILE"
  flock -n 9 || die "已有备份任务在运行（$LOCK_FILE）"
}

# 备份目录本身在同一块盘时给出明确警告：这不是备份，只是快照
warn_if_not_offsite() {
  if [ -n "$OFFSITE_DIR" ]; then return 0; fi
  warn "未配置 OFFSITE_DIR：备份与业务数据在同一台机器/同一块盘，"
  warn "磁盘损坏或实例释放会同时丢失；生产请挂载 NAS 或同步到对象存储/另一台机器。"
}

# sha256 校验（有 .sha256 才校验）
verify_checksum() {
  local file="$1"
  [ -f "$file.sha256" ] || { warn "缺少校验文件 $file.sha256，跳过校验"; return 0; }
  ( cd "$(dirname -- "$file")" && sha256sum -c "$(basename -- "$file").sha256" ) >/dev/null \
    || die "校验失败：$file 与 .sha256 不一致（文件损坏或传输不完整）"
  log "校验通过：$(basename -- "$file")"
}
