"""ORM 模型包（22 张表，数据库设计 §3）。

Alembic ``autogenerate`` 依赖本包导入全部模型；**新增模型后必须在此登记**，
否则 ``migrations/env.py`` 的 ``Base.metadata`` 不包含该表。

分组：
- 业务：users / data_sources / datasource_types / raw_data / cleaned_data /
  analysis_results / knowledge_base / reports / tasks / api_keys / audit_logs /
  webhooks（12 张）
- RAG 评测：qa_datasets / qa_dataset_versions / qa_dataset_items（3 张，Phase 1）
  + rag_traces（1 张，Phase 2；评测结果表推迟到 Phase 3）
- Prompt：prompt_versions / prompt_usage_logs / version_rollback_logs（3 张）
- 可观测：llm_calls（1 张）
- 凭据：user_llm_credentials（1 张，BYOK）
"""
from app.models.analysis import AnalysisResult, KnowledgeBase, KnowledgeGap
from app.models.base import Base
from app.models.datasource import CleanedData, DataSource, RawData
from app.models.datasource_type import DataSourceType
from app.models.llm_call import LlmCall
from app.models.llm_credential import UserLLMCredential
from app.models.prompt import PromptUsageLog, PromptVersion, VersionRollbackLog
from app.models.qa_dataset import QaDataset, QaDatasetItem, QaDatasetVersion
from app.models.rag import RagTrace
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
    "DataSourceType",
    "KnowledgeBase",
    "KnowledgeGap",
    "LlmCall",
    "PromptUsageLog",
    "PromptVersion",
    "QaDataset",
    "QaDatasetItem",
    "QaDatasetVersion",
    "RagTrace",
    "RawData",
    "Report",
    "Task",
    "User",
    "UserLLMCredential",
    "VersionRollbackLog",
    "Webhook",
]
