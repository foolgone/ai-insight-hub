#!/usr/bin/env sh
# 容器启动入口：先执行数据库迁移，再启动进程（B-703 验收口径）
set -e

echo "[entrypoint] running alembic upgrade head ..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
