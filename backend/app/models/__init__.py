"""ORM 模型包（15 张表，数据库设计 §3）。

Alembic ``autogenerate`` 依赖本包导入全部模型；**新增模型后必须在此登记**，
否则 ``migrations/env.py`` 的 ``Base.metadata`` 不包含该表。

分组：
- 业务：users / data_sources / raw_data / cleaned_data / analysis_results /
  knowledge_base / reports / tasks / api_keys / audit_logs / webhooks（11 张）
- Prompt：prompt_versions / prompt_usage_logs / version_rollback_logs（3 张）
- 可观测：llm_calls（1 张）
"""
from app.models.analysis import AnalysisResult, KnowledgeBase
from app.models.base import Base
from app.models.datasource import CleanedData, DataSource, RawData
from app.models.llm_call import LlmCall
from app.models.prompt import PromptUsageLog, PromptVersion, VersionRollbackLog
from app.models.report import Report
from app.models.security import ApiKey, AuditLog, Webhook
from app.models.task import Task
from app.models.user import User

__all__ = [
    "AnalysisResult",
    "ApiKey",
    "AuditLog",
    "Base",
    "CleanedData",
    "DataSource",
    "KnowledgeBase",
    "LlmCall",
    "PromptUsageLog",
    "PromptVersion",
    "RawData",
    "Report",
    "Task",
    "User",
    "VersionRollbackLog",
    "Webhook",
]
