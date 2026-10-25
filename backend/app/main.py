"""
FastAPI 应用主入口

配置全部来自 app.core.config.settings（事实源），不在本文件写死端口、前缀或域名。
"""
from fastapi import APIRouter, FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import router as api_v1_router
from app.core import metrics  # noqa: F401  导入即注册 Prometheus 指标
from app.core.config import settings
from app.core.errors import (
    aiinsight_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import AIInsightHubException
from app.middleware.degradation_middleware import DegradationMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.logger import logger, setup_logging

# 结构化日志（Loguru）：启动即落文件日志（B-202）
setup_logging()

# 业务 API 路由（基础路径由配置决定，默认 /api/v1）
api_router = APIRouter(prefix=settings.API_V1_PREFIX, tags=["system"])

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="AI 驱动的智能对话数据分析平台",
    version=settings.APP_VERSION,
)

# CORS 配置（允许的来源来自 .env 的 BACKEND_CORS_ORIGINS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流（B-211：Redis 固定窗口，60 请求/分钟，超限 429 + X-RateLimit-*）
app.add_middleware(RateLimitMiddleware)

# 成本降级（B-316：STOPPED 返回 429，响应头 X-Cost-*；D-09 只告警不切模型）
app.add_middleware(DegradationMiddleware)

# 统一错误响应（B-201：所有失败均为 {"error": {"code", "message", "details"?}}）
app.add_exception_handler(AIInsightHubException, aiinsight_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "ai-insight-hub-api",
        "version": settings.APP_VERSION,
    }


@api_router.get("/health")
async def api_health_check():
    """健康检查（业务前缀下，默认 /api/v1/health）"""
    return {
        "status": "healthy",
        "service": "ai-insight-hub-api",
        "version": settings.APP_VERSION,
    }


api_router.include_router(api_v1_router)

app.include_router(api_router)


# Prometheus 指标端点（自建可观测方案：Loguru + DB 调用记录 + Prometheus，不使用 LangSmith）
if settings.PROMETHEUS_ENABLED:
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        @app.get(settings.METRICS_PATH, include_in_schema=False)
        async def prometheus_metrics() -> Response:
            """Prometheus 抓取端点（固定路径，避免 mount 产生的 307 重定向）。"""
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    except ImportError:  # pragma: no cover
        logger.warning("prometheus_client 未安装，已跳过 {} 端点", settings.METRICS_PATH)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
