#!/usr/bin/env sh
# 容器启动入口：先执行数据库迁移，再启动进程（B-703 验收口径）
set -e

echo "[entrypoint] running alembic upgrade head ..."
alembic upgrade head

# 演示数据（幂等；失败不阻塞启动）。需要把被访客改乱的数据恢复时，手动执行
#   python scripts/seed_demo.py --reset
if [ "${SEED_DEMO_DATA_ON_START:-1}" = "1" ]; then
  echo "[entrypoint] seeding demo data ..."
  python scripts/seed_demo.py || echo "[entrypoint] seed demo data skipped"
fi

echo "[entrypoint] starting: $*"
exec "$@"
