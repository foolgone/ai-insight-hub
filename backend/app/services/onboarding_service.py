"""导入引导与 ``workflow_status`` 推进（B-501）。

``workflow_status`` 合法取值（数据库约束）：
created → data_uploaded → data_cleaned → knowledge_built → ready。
只允许向前推进；非法取值或状态倒退抛 ``ValueError``（调用方转 400）。
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataSourceNotFoundError
from app.models import DataSource
from app.services.knowledge_status import (
    READY_THRESHOLD,
    KnowledgeStage,
    count_knowledge,
    get_knowledge_status,
    stage_for_count,
)

WORKFLOW_STATUSES: tuple[str, ...] = (
    "created",
    "data_uploaded",
    "data_cleaned",
    "knowledge_built",
    "ready",
)
_WORKFLOW_ORDER: dict[str, int] = {status: index for index, status in enumerate(WORKFLOW_STATUSES)}

_NEXT_ACTION = {
    "created": "上传对话数据（CSV/JSON/XLSX/TXT）",
    "data_uploaded": "执行数据清洗",
    "data_cleaned": "执行知识提取（或初始化种子知识库）",
    "knowledge_built": "补充知识至 50 条，或执行质量评估/报告生成",
    "ready": "知识库已就绪：可检索 FAQ、生成报告",
}


async def update_workflow_status(
    session: AsyncSession,
    *,
    datasource_id: uuid.UUID,
    status: str,
) -> DataSource:
    """推进数据源工作流状态（只允许前进）。"""
    if status not in _WORKFLOW_ORDER:
        raise ValueError(f"invalid workflow_status: {status}")
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    current = _WORKFLOW_ORDER.get(datasource.workflow_status, -1)
    if _WORKFLOW_ORDER[status] < current:
        raise ValueError(
            f"cannot move workflow_status backwards: " f"{datasource.workflow_status} -> {status}"
        )
    if datasource.workflow_status != status:
        datasource.workflow_status = status
        await session.flush()
        await session.refresh(datasource)
    return datasource


async def maybe_mark_knowledge_built(
    session: AsyncSession, *, datasource_id: uuid.UUID
) -> DataSource:
    """按知识条数推进到 knowledge_built / ready。"""
    total = await count_knowledge(session, datasource_id)
    if total >= READY_THRESHOLD:
        target = "ready"
    elif total >= 1:
        target = "knowledge_built"
    else:
        target = "data_cleaned"
    return await update_workflow_status(session, datasource_id=datasource_id, status=target)


async def onboarding_status(session: AsyncSession, datasource_id: uuid.UUID) -> dict:
    """返回工作流状态 + 冷启动三态 + 下一步动作。"""
    datasource = await session.get(DataSource, datasource_id)
    if datasource is None or datasource.deleted_at is not None:
        raise DataSourceNotFoundError(details={"datasource_id": str(datasource_id)})
    knowledge = await get_knowledge_status(session, datasource_id)
    stage = KnowledgeStage(knowledge["stage"])
    return {
        "datasource_id": str(datasource_id),
        "workflow_status": datasource.workflow_status,
        "knowledge": knowledge,
        "next_action": _NEXT_ACTION.get(datasource.workflow_status, _NEXT_ACTION["created"]),
        "ready": datasource.workflow_status == "ready" or stage is KnowledgeStage.READY,
    }


def knowledge_built_status_for(total: int) -> str:
    """按知识条数推导应处的 workflow_status（纯函数，便于测试）。"""
    stage = stage_for_count(total)
    if stage is KnowledgeStage.READY:
        return "ready"
    if stage is KnowledgeStage.WARMING:
        return "knowledge_built"
    return "data_cleaned"


__all__ = [
    "WORKFLOW_STATUSES",
    "knowledge_built_status_for",
    "maybe_mark_knowledge_built",
    "onboarding_status",
    "update_workflow_status",
]
