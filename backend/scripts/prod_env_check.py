"""验收：生产环境变量模板校验（不启动服务，只验证可解析与关键不变量）。

运行：backend 目录
    .\\venv\\Scripts\\python.exe scripts\\prod_env_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / ".env.production.example"


def main() -> int:
    if not TEMPLATE.exists():
        print(f"[FAIL] 模板不存在：{TEMPLATE}")
        return 1
    settings = Settings(_env_file=str(TEMPLATE))  # type: ignore[call-arg]

    # BYOK：密钥模板允许留空（部署时注入），但一旦填写必须是合法的 Fernet 密钥
    credential_key = settings.CREDENTIAL_ENCRYPTION_KEY.strip()
    fernet_ok = False
    if credential_key:
        try:
            from cryptography.fernet import Fernet

            Fernet(credential_key.encode())
            fernet_ok = True
        except (ValueError, TypeError):
            fernet_ok = False

    checks = [
        ("ENVIRONMENT=production", settings.ENVIRONMENT == "production"),
        ("DEBUG=False", settings.DEBUG is False),
        ("AUTH_COOKIE_SECURE=True", settings.AUTH_COOKIE_SECURE is True),
        ("CELERY_TASK_ALWAYS_EAGER=False", settings.CELERY_TASK_ALWAYS_EAGER is False),
        ("RATE_LIMIT_ENABLED=True", settings.RATE_LIMIT_ENABLED is True),
        ("PROMETHEUS_ENABLED=True", settings.PROMETHEUS_ENABLED is True),
        ("DATABASE_URL 指向 postgres 服务", "@postgres:" in settings.DATABASE_URL),
        ("REDIS_URL 指向 redis 服务", "redis:6379" in settings.REDIS_URL),
        ("CORS 为列表解析成功", isinstance(settings.BACKEND_CORS_ORIGINS, list)),
        ("JWT_SECRET_KEY 已填写（占位符）", bool(settings.JWT_SECRET_KEY)),
        ("LLM_PRICE 已配置（模板为 0，需填真实值）", settings.LLM_PRICE_INPUT_PER_MTOK > 0),
        # BYOK 生产不变量（见开发指南 §8.3）
        ("BYOK_ENABLED=True", settings.BYOK_ENABLED is True),
        (
            "ALLOW_SERVER_KEY_FALLBACK=False（生产绝不回退服务端 Key）",
            settings.ALLOW_SERVER_KEY_FALLBACK is False,
        ),
        ("CREDENTIAL_ENCRYPTION_KEY 为合法 Fernet 密钥（部署时注入）", fernet_ok),
        (
            "SEED_DEMO_PASSWORD 与登录页展示一致（demo123）",
            settings.SEED_DEMO_PASSWORD == "demo123",
        ),
    ]
    failed = 0
    for name, ok in checks:
        print(f"[{'OK  ' if ok else 'WARN'}] {name}")
        if not ok:
            failed += 1

    placeholders = []
    for field in (
        "DEEPSEEK_API_KEY",
        "JWT_SECRET_KEY",
        "SEED_ADMIN_EMAIL",
        "CREDENTIAL_ENCRYPTION_KEY",
    ):
        value = str(getattr(settings, field, ""))
        if not value.strip() or "CHANGE_ME" in value or "change-me" in value.lower():
            placeholders.append(field)
    print(f"\n模板解析：OK；待替换占位符：{', '.join(placeholders) if placeholders else '无'}")
    print("提示：生成密钥 → python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
    print(
        "提示：bcrypt 哈希 → python -c "
        "\"from app.core.security import hash_password; print(hash_password('你的密码'))\""
    )
    print(
        '提示：Fernet 密钥 → python -c "from cryptography.fernet import Fernet; '
        "print(Fernet.generate_key().decode())\""
    )
    # 模板本身允许占位符；只把「结构性错误」视为失败（如解析失败/生产不变量为假）
    # CREDENTIAL_ENCRYPTION_KEY 属于"部署时注入"，模板留空不算结构性问题
    structural = [
        name
        for name, ok in checks
        if not ok and "LLM_PRICE" not in name and "CREDENTIAL_ENCRYPTION_KEY" not in name
    ]
    if structural:
        print(f"[FAIL] 结构性问题：{structural}")
        return 1
    print("[PASS] 生产 env 模板结构校验通过（占位符需在部署时替换）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
