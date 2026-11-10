"""仓储层：把 SQL 收敛在一处，service 只表达「要什么」，不关心「怎么查」。

分层位置：``api → services → repositories → models``。
仓储层不得反向依赖 services / application / agents / api（import-linter 有契约守着）。
"""
from app.repositories import analysis_results, cleaned_data, knowledge_base, raw_data

__all__ = ["analysis_results", "cleaned_data", "knowledge_base", "raw_data"]
