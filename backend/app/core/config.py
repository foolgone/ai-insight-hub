"""
应用配置

- 唯一入口：本文件是后端配置项的事实源，必须与 `backend/.env.example` 保持一一对应。
- LLM：DeepSeek V4.1 Flash（OpenAI 兼容协议，由自研 `app/core/llm.py::LLMClient` 直连；
  不使用 LangChain/LangGraph，见 docs/04-development/13-ADR-001），模型 id 不写死在代码里，
  统一从 `DEFAULT_LLM_MODEL` 读取，便于后续切换模型而不改业务代码。
- 可观测：Loguru 结构化日志 + 数据库调用记录 + Prometheus 指标（不使用 LangSmith SaaS）。
"""
from functools import lru_cache
from typing import Literal

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
    # 默认模型 id 由配置决定，业务代码不写死；已实测可用：deepseek-flash（2026-10-24，
    # 高阶备选 deepseek-v4-pro 本 MVP 不用）
    DEFAULT_LLM_MODEL: str = "deepseek-flash"
    # 结构化输出（清洗/提取/评估）默认温度为 0；洞察/报告类 Agent 可单独覆盖为 0.3
    DEFAULT_TEMPERATURE: float = 0.0
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_TIMEOUT: int = 60

    # ---------------- 嵌入（sentence-transformers，本地离线缓存） ----------------
    # 默认多语言 MiniLM（384 维，与 embedding 表结构一致）；离线部署时把
    # EMBEDDING_CACHE_DIR 指向本地模型目录，避免联网下载。
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_CACHE_DIR: str = ""

    # ---------------- 知识提取成本优化（T9 Phase 1） ----------------
    # 规则去重：只合并「问题 + 答案归一化后完全相同」的对话（零语义风险）
    EXTRACTION_RULE_DEDUP_ENABLED: bool = True
    # 既有问题语义 top-k；0 表示关闭，回退旧行为（全部问题 → Agent 截前 30 条）
    EXTRACTION_QUESTION_TOPK: int = 8
    # 语义选优查询文本的截断长度（字符）
    EXTRACTION_QUESTION_QUERY_CHARS: int = 800

    # 成本核算单价（USD / 百万 token）
    # ⚠️ 代码不写死单价：默认 0.0 表示「未配置」，成本计算时须检测并告警；实际值填在 .env
    LLM_PRICE_INPUT_PER_MTOK: float = 0.0
    LLM_PRICE_OUTPUT_PER_MTOK: float = 0.0
    # 成本超限时的降级模型（空字符串表示未启用降级）
    DEGRADED_LLM_MODEL: str = ""

    # ---------------- 可观测（自建，替代 LangSmith） ----------------
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LLM_CALL_LOG_ENABLED: bool = True  # 是否把每次 LLM 调用写入数据库
    PROMETHEUS_ENABLED: bool = True  # 是否暴露 /metrics
    METRICS_PATH: str = "/metrics"
    # Sentry 错误追踪（T7）：DSN 为空时完全 no-op，不影响启动
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_SEND_DEFAULT_PII: bool = False

    # ---------------- 文件存储（MinIO/S3） ----------------
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_UPLOADS: str = "aiinsight-uploads"
    MINIO_BUCKET_REPORTS: str = "aiinsight-reports"
    MINIO_USE_SSL: bool = False
    # 存储后端：auto（MinIO 不可用时回退本地）| minio | local
    STORAGE_BACKEND: str = "auto"
    # 本地回退目录（相对 backend 工作目录）
    STORAGE_LOCAL_DIR: str = ".storage/uploads"

    # ---------------- 认证（JWT） ----------------
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-this"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------------- 认证 Cookie（T4：refresh token 只放 HttpOnly Cookie） ----------------
    AUTH_COOKIE_NAME: str = "aiih_refresh"
    AUTH_COOKIE_PATH: str = "/api/v1/auth"
    # 生产（HTTPS）必须为 true；SameSite=None 时同样要求 Secure
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_DOMAIN: str | None = None

    # ---------------- 成本控制 ----------------
    DAILY_COST_LIMIT: float = 100.0
    MONTHLY_COST_LIMIT: float = 3000.0
    COST_ALERT_THRESHOLD: float = 0.8

    # ---------------- Celery ----------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    # 测试/本地联调：True 时任务同步执行（不依赖 worker，便于集成测试）
    CELERY_TASK_ALWAYS_EAGER: bool = False

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
