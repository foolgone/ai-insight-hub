#!/usr/bin/env bash
# 恢复演练：备份 → 还原到临时库 → 逐表比对 → 清理。
#
# 目的：把「备份能不能恢复」从口号变成可重复执行、有明确 PASS/FAIL 的动作。
# 建议每月跑一次，以及每次「数据结构/迁移」变更后跑一次。
#
# 用法：
#   ./ops/backup/drill.sh                 # 现场备份一份再还原验证
#   ./ops/backup/drill.sh --no-backup     # 用最新的历史备份验证（不产生新备份）
#   ./ops/backup/drill.sh --from <dump>   # 指定某个备份验证
#   ./ops/backup/drill.sh --keep          # 保留演练库，便于人工抽查
set -euo pipefail
source "$(cd -- "$(dirname -- "$0")" && pwd)/common.sh"

FROM=""
DO_BACKUP=1
KEEP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --no-backup) DO_BACKUP=0; shift ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "未知参数：$1（-h 查看用法）" ;;
  esac
done

require_stack
PROD_DB="$(pg_db)"
DRILL_DB="${PROD_DB}_drill_$(date +%Y%m%d_%H%M%S)"
FAILURES=0
FAIL_MSG=""

problem() {
  FAIL_MSG="${FAIL_MSG}  - $*"$'\n'
  FAILURES=$((FAILURES + 1))
  warn "断言失败：$*"
}

cleanup() {
  if [ "$KEEP" = 1 ]; then
    log "保留演练库 $DRILL_DB（用完请手动 drop）"
    return 0
  fi
  psql_db postgres "drop database if exists \"$DRILL_DB\" with (force)" >/dev/null 2>&1 \
    && log "已清理演练库 $DRILL_DB" \
    || warn "清理演练库失败：$DRILL_DB"
}
trap cleanup EXIT

if [ -z "$FROM" ]; then
  if [ "$DO_BACKUP" = 1 ]; then
    log "步骤 1/3：生成一份新备份（仅 PG）"
    "$SCRIPT_DIR/backup.sh" --no-minio
  fi
  FROM="$(find "$BACKUP_DIR/pg" -maxdepth 1 -type f -name '*.dump' -printf '%T@ %p\n' \
    | sort -nr | head -1 | cut -d' ' -f2-)"
fi
[ -n "$FROM" ] && [ -f "$FROM" ] || die "找不到可用于演练的 dump（先跑一次 backup.sh）"
log "使用备份：$FROM（$(du -h "$FROM" | cut -f1)）"

log "步骤 2/3：还原到临时库 $DRILL_DB"
"$SCRIPT_DIR/restore.sh" "$FROM" --db "$DRILL_DB" --yes

log "步骤 3/3：比对线上库 $PROD_DB 与演练库"
PROD_HEAD="$(psql_db "$PROD_DB" "select version_num from alembic_version" 2>/dev/null || true)"
DRILL_HEAD="$(psql_db "$DRILL_DB" "select version_num from alembic_version" 2>/dev/null || true)"
if [ "$PROD_HEAD" = "$DRILL_HEAD" ] && [ -n "$DRILL_HEAD" ]; then
  log "alembic_version 一致：$DRILL_HEAD"
else
  problem "alembic_version 不一致（prod=${PROD_HEAD:-<空>} drill=${DRILL_HEAD:-<空>}）"
fi

if [ "$(psql_db "$DRILL_DB" "select count(*) from pg_extension where extname='vector'")" = "1" ]; then
  log "vector 扩展存在"
else
  problem "演练库缺少 vector 扩展"
fi

PROD_TABLES="$(psql_db "$PROD_DB" "select tablename from pg_tables where schemaname='public' order by 1")"
DRILL_TABLES="$(psql_db "$DRILL_DB" "select tablename from pg_tables where schemaname='public' order by 1")"
MISSING="$(comm -23 <(printf '%s\n' "$PROD_TABLES") <(printf '%s\n' "$DRILL_TABLES") | tr '\n' ' ')"
EXTRA="$(comm -13 <(printf '%s\n' "$PROD_TABLES") <(printf '%s\n' "$DRILL_TABLES") | tr '\n' ' ')"
if [ -z "${MISSING// }" ] && [ -z "${EXTRA// }" ]; then
  log "表结构一致：$(printf '%s\n' "$PROD_TABLES" | sed '/^$/d' | wc -l) 张表"
else
  [ -n "${MISSING// }" ] && problem "演练库缺表：$MISSING"
  [ -n "${EXTRA// }" ] && problem "演练库多表：$EXTRA"
fi

ROWS_CHECKED=0
MISMATCH_TABLES=""
while IFS= read -r table; do
  [ -n "$table" ] || continue
  prod_rows="$(psql_db "$PROD_DB" "select count(*) from \"$table\"" 2>/dev/null || echo "?")"
  drill_rows="$(psql_db "$DRILL_DB" "select count(*) from \"$table\"" 2>/dev/null || echo "?")"
  ROWS_CHECKED=$((ROWS_CHECKED + 1))
  [ "$prod_rows" = "$drill_rows" ] || MISMATCH_TABLES="${MISMATCH_TABLES}${table}(prod=${prod_rows},drill=${drill_rows}) "
done < <(printf '%s\n' "$PROD_TABLES")

if [ -z "$MISMATCH_TABLES" ]; then
  log "行数一致：$ROWS_CHECKED 张表逐表比对通过"
else
  problem "行数不一致：$MISMATCH_TABLES"
fi

if [ "$FAILURES" -eq 0 ]; then
  printf '\n恢复演练 PASS：%s → %s（%s 张表结构+行数全部一致）\n' \
    "$(basename -- "$FROM")" "$DRILL_DB" "$ROWS_CHECKED"
  exit 0
fi

printf '\n恢复演练 FAIL（%s 项）：\n%s\n' "$FAILURES" "$FAIL_MSG" >&2
exit 1
