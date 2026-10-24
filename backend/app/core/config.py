"""
应用配置

- 唯一入口：本文件是后端配置项的事实源，必须与 `backend/.env.example` 保持一一对应。
- LLM：DeepSeek V4.1 Flash（通过 langchain-deepseek 官方集成接入），模型 id 不写死在代码里，
  统一从 `DEFAULT_LLM_MODEL` 读取，便于后续切换模型而不改业务代码。
- 可观测：Loguru 结构化日志 + 数据库调用记录 + Prometheus 指标（不使用 LangSmith SaaS）。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---------------- 应用 ----------------
    APP_NAME: str = "AI Insight Hub"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # ---------------- API ----------------
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ---------------- 数据库 ----------------
    DATABASE_URL: str = "postgresql://aiinsight:dev_password@localhost:5432/aiinsight"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # ---------------- Redis ----------------
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # ---------------- LLM（DeepSeek） ----------------
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    # 默认模型 id 由配置决定，业务代码不写死；实际可用 id 以 DeepSeek 官方为准
    DEFAULT_LLM_MODEL: str = "deepseek-v4.1-flash"
    # 结构化输出（清洗/提取/评估）默认温度为 0；洞察/报告类 Agent 可单独覆盖为 0.3
    DEFAULT_TEMPERATURE: float = 0.0
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_TIMEOUT: int = 60

    # 成本核算单价（USD / 百万 token）
    # ⚠️ 代码不写死单价：默认 0.0 表示「未配置」，成本计算时须检测并告警；实际值填在 .env
    LLM_PRICE_INPUT_PER_MTOK: float = 0.0
    LLM_PRICE_OUTPUT_PER_MTOK: float = 0.0
    # 成本超限时的降级模型（空字符串表示未启用降级）
    DEGRADED_LLM_MODEL: str = ""

    # ---------------- 可观测（自建，替代 LangSmith） ----------------
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LLM_CALL_LOG_ENABLED: bool = True          # 是否把每次 LLM 调用写入数据库
    PROMETHEUS_ENABLED: bool = True            # 是否暴露 /metrics
    METRICS_PATH: str = "/metrics"

    # ---------------- 文件存储（MinIO/S3） ----------------
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_UPLOADS: str = "aiinsight-uploads"
    MINIO_BUCKET_REPORTS: str = "aiinsight-reports"
    MINIO_USE_SSL: bool = False

    # ---------------- 认证（JWT） ----------------
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-this"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------------- 成本控制 ----------------
    DAILY_COST_LIMIT: float = 100.0
    MONTHLY_COST_LIMIT: float = 3000.0
    COST_ALERT_THRESHOLD: float = 0.8

    # ---------------- Celery ----------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ---------------- 邮件告警（可选） ----------------
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@aiinsight.com"

    # ---------------- 速率限制 ----------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # ---------------- 文件上传 ----------------
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_EXTENSIONS: str = "csv,json,xlsx,txt"


@lru_cache
def get_settings() -> Settings:
    """带缓存的配置读取（测试中可用 get_settings.cache_clear() 重置）"""
    return Settings()


settings = get_settings()
