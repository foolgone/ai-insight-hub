"""
FastAPI 应用主入口
"""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 业务 API 路由（基础路径与架构文档保持一致：/api/v1）
api_router = APIRouter(prefix="/api/v1", tags=["system"])

app = FastAPI(
    title="AI Insight Hub API",
    description="AI 驱动的智能对话数据分析平台",
    version="0.1.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 前端开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to AI Insight Hub API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "ai-insight-hub-api"
    }


@api_router.get("/health")
async def api_health_check():
    """健康检查（/api/v1）"""
    return {
        "status": "healthy",
        "service": "ai-insight-hub-api",
        "version": "0.1.0"
    }


app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
