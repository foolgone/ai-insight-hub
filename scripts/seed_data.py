"""填充开发/演示用测试数据（幂等）。

依赖：数据库已初始化（docker-compose up -d）且已执行迁移（cd backend && alembic upgrade head）。

用法：
    cd backend
    .\\venv\\Scripts\\python.exe ..\\scripts\\seed_data.py
"""
import sys
from pathlib import Path

# 允许直接以脚本方式运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.core.config import settings  # noqa: E402

DEMO_EMAIL = "admin@aiinsight.com"
DEMO_PASSWORD = "admin123456"  # 仅用于本地开发，生产环境禁止使用


def _hash_password(raw: str) -> str:
    try:
        from passlib.context import CryptContext
    except ImportError:
        raise SystemExit(
            "缺少 passlib，请先执行：pip install -r backend/requirements.txt"
        ) from None
    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(raw)


def main() -> None:
    engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), future=True)

    tables = set(inspect(engine).get_table_names())
    required = {"users", "data_sources"}
    if not required.issubset(tables):
        missing = ", ".join(sorted(required - tables))
        raise SystemExit(
            f"数据库缺少表：{missing}\n"
            "请先执行：\n"
            "  1) docker-compose up -d\n"
            "  2) cd backend && .\\venv\\Scripts\\python.exe -m alembic upgrade head"
        )

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": DEMO_EMAIL}
        ).fetchone()
        if existing:
            print(f"已存在，跳过：{DEMO_EMAIL}")
        else:
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, name, role, is_active) "
                    "VALUES (:email, :pwd, :name, :role, TRUE)"
                ),
                {
                    "email": DEMO_EMAIL,
                    "pwd": _hash_password(DEMO_PASSWORD),
                    "name": "演示管理员",
                    "role": "admin",
                },
            )
            print(f"已创建演示用户：{DEMO_EMAIL} / {DEMO_PASSWORD}")

        ds_exists = conn.execute(
            text("SELECT id FROM data_sources WHERE name = :name"),
            {"name": "演示数据源"},
        ).fetchone()
        if ds_exists:
            print("已存在，跳过：演示数据源")
        else:
            conn.execute(
                text(
                    "INSERT INTO data_sources (name, type, description, status) "
                    "VALUES (:name, :type, :desc, :status)"
                ),
                {
                    "name": "演示数据源",
                    "type": "customer_service",
                    "desc": "seed_data.py 生成的演示数据源",
                    "status": "active",
                },
            )
            print("已创建演示数据源")

    engine.dispose()
    print("完成。")


if __name__ == "__main__":
    main()
