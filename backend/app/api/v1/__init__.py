"""API v1 路由聚合（B-212 逐步补齐各业务模块）。"""
from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    auth,
    datasources,
    knowledge,
    llm_credential,
    reports,
    tasks,
    users,
)

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(users.router, prefix="/users", tags=["用户"])
router.include_router(llm_credential.router, prefix="/users", tags=["用户"])
router.include_router(datasources.router, prefix="/datasources", tags=["数据源"])
router.include_router(analysis.router, prefix="/datasources", tags=["分析"])
router.include_router(knowledge.router, prefix="/datasources", tags=["知识库"])
router.include_router(reports.datasource_router, prefix="/datasources", tags=["报告"])
router.include_router(reports.router, prefix="/reports", tags=["报告"])
router.include_router(tasks.router, prefix="/tasks", tags=["任务"])

__all__ = ["router"]
