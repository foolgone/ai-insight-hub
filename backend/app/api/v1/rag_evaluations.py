"""RAG 批量评测 API（Phase 3C）。

- 创建/重试：落库后入队（先 commit，避免 worker 读不到）；
- 查询：Run 与 Task 状态分别返回，不混为一谈；
- 失败样本与结果列表支持 metric/status 过滤。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import pagination_params, require_roles
from app.composition import enqueue
from app.core.database import get_db
from app.core.pagination import PaginationParams
from app.models import RagEvaluationRun, Task, User
from app.schemas.base import Page
from app.schemas.rag_evaluation import (
    RagEvaluationCreate,
    RagEvaluationCreated,
    RagEvaluationResultRead,
    RagEvaluationRunListItem,
    RagEvaluationRunRead,
    EvaluationSummaryGroup,
    RagEvaluationSummary,
)
from app.services import rag_evaluation_service as service

router = APIRouter()

READ_ROLES = ("admin", "user", "viewer")
WRITE_ROLES = ("admin", "user")


async def _tasks_by_id(
    session: AsyncSession, runs: list[RagEvaluationRun]
) -> dict[uuid.UUID, Task]:
    ids = [run.task_id for run in runs if run.task_id is not None]
    if not ids:
        return {}
    rows = await session.execute(select(Task).where(Task.id.in_(ids)))
    return {task.id: task for task in rows.scalars().all()}


def _run_read(run: RagEvaluationRun, task: Task | None) -> RagEvaluationRunRead:
    return RagEvaluationRunRead(
        id=run.id,
        task_id=run.task_id,
        task_status=task.status if task else None,
        task_progress=task.progress if task else None,
        parent_run_id=run.parent_run_id,
        attempt=run.attempt,
        retry_scope=run.retry_scope,
        dataset_id=run.dataset_id,
        dataset_name=run.dataset_name,
        dataset_version_id=run.dataset_version_id,
        dataset_checksum=run.dataset_checksum,
        execution_mode=run.execution_mode,
        adapter=run.adapter,
        retrieval_config=dict(run.retrieval_config or {}),
        judge_config=dict(run.judge_config or {}),
        config_snapshot=dict(run.config_snapshot or {}),
        item_selection=dict(run.item_selection or {}),
        total_items=run.total_items,
        completed_items=run.completed_items,
        skipped_items=run.skipped_items,
        failed_items=run.failed_items,
        status=run.status,
        aggregate=run.aggregate,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


def _run_list_item(run: RagEvaluationRun, task: Task | None) -> RagEvaluationRunListItem:
    return RagEvaluationRunListItem(
        id=run.id,
        task_id=run.task_id,
        task_status=task.status if task else None,
        parent_run_id=run.parent_run_id,
        attempt=run.attempt,
        dataset_name=run.dataset_name,
        dataset_version_id=run.dataset_version_id,
        execution_mode=run.execution_mode,
        adapter=run.adapter,
        total_items=run.total_items,
        completed_items=run.completed_items,
        skipped_items=run.skipped_items,
        failed_items=run.failed_items,
        status=run.status,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


async def _dispatch(session: AsyncSession, run: RagEvaluationRun, task: Task) -> None:
    """入队；失败时把 Run/Task 标记为 failed，用户可重试（不留下永远 pending 的僵尸行）。"""
    try:
        task.celery_task_id = enqueue.enqueue_rag_evaluation(str(run.id))
    except Exception as exc:  # noqa: BLE001 - broker 故障要落到 Run 上
        run.status = service.RUN_FAILED
        run.error_message = f"enqueue_failed: {exc}"[:1000]
        run.completed_at = service.now_naive()
        task.status = "failed"
        task.error_message = "enqueue_failed"
        task.completed_at = service.now_naive()
        await session.commit()
        raise
    await session.flush()


def _result_read(row) -> RagEvaluationResultRead:  # noqa: ANN001 - ORM 行
    return RagEvaluationResultRead(
        id=row.id,
        run_id=row.run_id,
        dataset_item_id=row.dataset_item_id,
        trace_id=row.trace_id,
        metric_name=row.metric_name,
        metric_version=row.metric_version,
        status=row.status,
        score=row.score,
        skipped_reason=row.skipped_reason,
        details=dict(row.details or {}),
        judge_config=dict(row.judge_config or {}),
        raw_output=row.raw_output,
        raw_truncated=row.raw_truncated,
        latency_ms=row.latency_ms,
        error_message=row.error_message,
        created_at=row.created_at,
    )


@router.post(
    "",
    response_model=RagEvaluationCreated,
    response_model_by_alias=False,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建批量评测（202）",
)
async def create_evaluation(
    payload: RagEvaluationCreate,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagEvaluationCreated:
    run, task = await service.create_run(session, user=user, payload=payload)
    # 先提交 Run/Task，避免 worker 抢跑读不到；入队失败时把两者标记失败（可重试）
    await session.commit()
    await _dispatch(session, run, task)
    return RagEvaluationCreated(run_id=run.id, task_id=task.id, status=run.status)


@router.get(
    "",
    response_model=Page[RagEvaluationRunListItem],
    response_model_by_alias=False,
    summary="评测 Run 列表",
)
async def list_evaluations(
    dataset_id: uuid.UUID | None = Query(default=None),
    dataset_version_id: uuid.UUID | None = Query(default=None),
    run_status: str | None = Query(default=None, alias="status", max_length=20),
    execution_mode: str | None = Query(default=None, max_length=20),
    adapter: str | None = Query(default=None, max_length=50),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[RagEvaluationRunListItem]:
    runs, pagination = await service.list_runs(
        session,
        user=user,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        status=run_status,
        execution_mode=execution_mode,
        adapter=adapter,
        params=params,
    )
    tasks = await _tasks_by_id(session, runs)
    return Page[RagEvaluationRunListItem](
        items=[
            _run_list_item(run, tasks.get(run.task_id) if run.task_id else None) for run in runs
        ],
        pagination=pagination,
    )


@router.get(
    "/summary",
    response_model=RagEvaluationSummary,
    response_model_by_alias=False,
    summary="跨 Run 分组汇总（doc/conv、mode、adapter、metric_version 分组）",
)
async def evaluation_summary(
    dataset_id: uuid.UUID | None = Query(default=None),
    execution_mode: str | None = Query(default=None, max_length=20),
    adapter: str | None = Query(default=None, max_length=50),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagEvaluationSummary:
    groups = await service.summary(
        session,
        user=user,
        dataset_id=dataset_id,
        execution_mode=execution_mode,
        adapter=adapter,
    )
    return RagEvaluationSummary(
        groups=[EvaluationSummaryGroup.model_validate(group) for group in groups]
    )


@router.get(
    "/{run_id}",
    response_model=RagEvaluationRunRead,
    response_model_by_alias=False,
    summary="Run 详情（含 Task 状态、聚合）",
)
async def get_evaluation(
    run_id: uuid.UUID,
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagEvaluationRunRead:
    run = await service.get_run(session, user=user, run_id=run_id)
    task = await session.get(Task, run.task_id) if run.task_id else None
    return _run_read(run, task)


@router.get(
    "/{run_id}/results",
    response_model=Page[RagEvaluationResultRead],
    response_model_by_alias=False,
    summary="Run 结果列表",
)
async def list_evaluation_results(
    run_id: uuid.UUID,
    metric_name: str | None = Query(default=None, max_length=40),
    result_status: str | None = Query(default=None, alias="status", max_length=20),
    dataset_item_id: uuid.UUID | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[RagEvaluationResultRead]:
    rows, pagination = await service.list_results(
        session,
        user=user,
        run_id=run_id,
        metric_name=metric_name,
        status=result_status,
        dataset_item_id=dataset_item_id,
        params=params,
    )
    return Page[RagEvaluationResultRead](
        items=[_result_read(row) for row in rows], pagination=pagination
    )


@router.get(
    "/{run_id}/failures",
    response_model=Page[RagEvaluationResultRead],
    response_model_by_alias=False,
    summary="失败样本（status=failed）",
)
async def list_evaluation_failures(
    run_id: uuid.UUID,
    metric_name: str | None = Query(default=None, max_length=40),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(require_roles(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> Page[RagEvaluationResultRead]:
    rows, pagination = await service.list_results(
        session,
        user=user,
        run_id=run_id,
        metric_name=metric_name,
        status="failed",
        dataset_item_id=None,
        params=params,
    )
    return Page[RagEvaluationResultRead](
        items=[_result_read(row) for row in rows], pagination=pagination
    )


@router.post(
    "/{run_id}/retry",
    response_model=RagEvaluationCreated,
    response_model_by_alias=False,
    status_code=status.HTTP_202_ACCEPTED,
    summary="重试失败样本（新建 Run，保留历史）",
)
async def retry_evaluation(
    run_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagEvaluationCreated:
    run, task = await service.retry_run(session, user=user, run_id=run_id)
    await session.commit()
    await _dispatch(session, run, task)
    return RagEvaluationCreated(run_id=run.id, task_id=task.id, status=run.status)


@router.post(
    "/{run_id}/cancel",
    response_model=RagEvaluationRunRead,
    response_model_by_alias=False,
    summary="取消评测",
)
async def cancel_evaluation(
    run_id: uuid.UUID,
    user: User = Depends(require_roles(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> RagEvaluationRunRead:
    run = await service.cancel_run(session, user=user, run_id=run_id)
    task = await session.get(Task, run.task_id) if run.task_id else None
    return _run_read(run, task)
