"""
FastAPI 应用主入口

配置全部来自 app.core.config.settings（事实源），不在本文件写死端口、前缀或域名。
"""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

try:  # loguru 未安装时降级到标准库日志，保证应用仍可启动
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

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


app.include_router(api_router)


# Prometheus 指标端点（自建可观测方案：Loguru + DB 调用记录 + Prometheus，不使用 LangSmith）
if settings.PROMETHEUS_ENABLED:
    try:
        from prometheus_client import make_asgi_app

        app.mount(settings.METRICS_PATH, make_asgi_app())
    except ImportError:  # pragma: no cover
        # 用 f-string 构造消息，兼容 loguru 与标准库 logging 两种后端的格式化差异
        logger.warning(f"prometheus_client 未安装，已跳过 {settings.METRICS_PATH} 端点")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
