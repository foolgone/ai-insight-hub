"""Celery 入队适配器（组合根）。

业务 service 只负责「建任务行 + 改状态」，**不持有 Celery 任务对象**；
真正的 ``.delay()`` 由这里执行。这样 ``app.tasks`` 成为纯叶子，
``services → tasks`` 的反向依赖（5 个函数内循环 import）彻底消失。
"""
from __future__ import annotations

__all__ = [
    "enqueue_clean",
    "enqueue_evaluation",
    "enqueue_extract",
    "enqueue_insight",
    "enqueue_report",
]


def enqueue_clean(task_id: str) -> str:
    from app.tasks.cleaning import clean_datasource

    return str(clean_datasource.delay(task_id).id)


def enqueue_evaluation(task_id: str) -> str:
    from app.tasks.evaluation import evaluate_datasource

    return str(evaluate_datasource.delay(task_id).id)


def enqueue_extract(task_id: str) -> str:
    from app.tasks.knowledge import extract_knowledge_task

    return str(extract_knowledge_task.delay(task_id).id)


def enqueue_insight(task_id: str) -> str:
    from app.tasks.insight import analyze_insights_task

    return str(analyze_insights_task.delay(task_id).id)


def enqueue_report(report_id: str) -> str:
    from app.tasks.report import generate_report_task

    return str(generate_report_task.delay(report_id).id)
