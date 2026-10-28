"""领域异常体系（开发规范 §2.3 + API 设计 §12.2）。

约定：
- 所有领域异常继承 ``AIInsightHubException``；
- ``code`` 为 API §12.2 的业务错误码，HTTP 状态码由 ``ERROR_STATUS`` 推导；
- 全局 handler 在 ``app.main`` 注册，输出统一 ``{"error": {...}}`` 结构。
"""
from __future__ import annotations

from typing import Any

from app.core.errors import ERROR_STATUS, ErrorCode, FrameworkErrorCode


class AIInsightHubException(Exception):
    """业务异常基类。"""

    code: ErrorCode | FrameworkErrorCode = ErrorCode.INTERNAL_ERROR
    default_message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        code: ErrorCode | FrameworkErrorCode | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.code = code or self.code
        self.message = message or self.default_message
        self.details = details
        self._status_code = status_code
        self.headers = headers
        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        if self._status_code is not None:
            return self._status_code
        return ERROR_STATUS.get(self.code, 500)


# --------------------------------------------------------------------------- 认证 / 权限
class AuthenticationError(AIInsightHubException):
    code = ErrorCode.AUTH_INVALID_CREDENTIALS
    default_message = "Invalid email or password"


class TokenExpiredError(AIInsightHubException):
    code = ErrorCode.AUTH_TOKEN_EXPIRED
    default_message = "Access token expired or revoked"


class RefreshTokenInvalidError(AIInsightHubException):
    code = ErrorCode.AUTH_REFRESH_TOKEN_INVALID
    default_message = "Refresh token invalid or expired"


class PermissionDeniedError(AIInsightHubException):
    code = ErrorCode.AUTH_FORBIDDEN
    default_message = "Permission denied"


class ApiKeyInvalidError(AIInsightHubException):
    code = ErrorCode.API_KEY_INVALID
    default_message = "API key invalid or revoked"


class ApiKeyScopeDeniedError(AIInsightHubException):
    code = ErrorCode.API_KEY_SCOPE_DENIED
    default_message = "API key scope denied"


# --------------------------------------------------------------------------- 资源不存在
class UserNotFoundError(AIInsightHubException):
    code = ErrorCode.USER_NOT_FOUND
    default_message = "User not found"


class DataSourceNotFoundError(AIInsightHubException):
    code = ErrorCode.DATASOURCE_NOT_FOUND
    default_message = "Data source not found"


class CleanedDataNotFoundError(AIInsightHubException):
    code = ErrorCode.CLEANED_DATA_NOT_FOUND
    default_message = "Cleaned data not found"


class TaskNotFoundError(AIInsightHubException):
    code = ErrorCode.TASK_NOT_FOUND
    default_message = "Task not found"


class FaqNotFoundError(AIInsightHubException):
    code = ErrorCode.FAQ_NOT_FOUND
    default_message = "FAQ not found"


class ReportNotFoundError(AIInsightHubException):
    code = ErrorCode.REPORT_NOT_FOUND
    default_message = "Report not found"


class ApiKeyNotFoundError(AIInsightHubException):
    code = ErrorCode.API_KEY_NOT_FOUND
    default_message = "API key not found"


class WebhookNotFoundError(AIInsightHubException):
    code = ErrorCode.WEBHOOK_NOT_FOUND
    default_message = "Webhook not found"


# --------------------------------------------------------------------------- 冲突
class UserEmailExistsError(AIInsightHubException):
    code = ErrorCode.USER_EMAIL_EXISTS
    default_message = "Email already registered"


class TaskAlreadyRunningError(AIInsightHubException):
    code = ErrorCode.TASK_ALREADY_RUNNING
    default_message = "A task of the same type is already running"


class TaskNotCancellableError(AIInsightHubException):
    code = ErrorCode.TASK_NOT_CANCELLABLE
    default_message = "Task already finished and cannot be cancelled"


class TaskNotRetryableError(AIInsightHubException):
    code = ErrorCode.TASK_NOT_RETRYABLE
    default_message = "Task is not in failed state and cannot be retried"


# --------------------------------------------------------------------------- 文件 / 校验
class FileTooLargeError(AIInsightHubException):
    code = ErrorCode.FILE_TOO_LARGE
    default_message = "Uploaded file exceeds the size limit"


class FileFormatInvalidError(AIInsightHubException):
    code = ErrorCode.FILE_FORMAT_INVALID
    default_message = "Unsupported file format"


class ReportFormatInvalidError(AIInsightHubException):
    code = ErrorCode.REPORT_FORMAT_INVALID
    default_message = "Invalid report type or format"


# --------------------------------------------------------------------------- 限流 / 配额 / 成本
class RateLimitExceededError(AIInsightHubException):
    code = ErrorCode.RATE_LIMIT_EXCEEDED
    default_message = "Too many requests"


class DataSourceQuotaExceededError(AIInsightHubException):
    code = ErrorCode.DATASOURCE_QUOTA_EXCEEDED
    default_message = "Data source quota exceeded"


class InsufficientCreditsError(AIInsightHubException):
    code = ErrorCode.INSUFFICIENT_CREDITS
    default_message = "Cost quota exhausted"


# --------------------------------------------------------------------------- BYOK 凭据
class LLMCredentialNotConfiguredError(AIInsightHubException):
    """未配置用户 Key 且未开启 fallback（428）。"""

    code = ErrorCode.LLM_CREDENTIAL_NOT_CONFIGURED
    default_message = "请先配置您自己的 DeepSeek API Key"


class LLMCredentialInvalidError(AIInsightHubException):
    """Key 格式非法 / 连通性校验失败 / 已标记 invalid（400）。"""

    code = ErrorCode.LLM_CREDENTIAL_INVALID
    default_message = "API Key 无效或已失效，请更新后再试"


class LLMCredentialDecryptError(AIInsightHubException):
    """加密密钥缺失/非法，或密文无法解密（500）。"""

    code = ErrorCode.LLM_CREDENTIAL_DECRYPT_FAILED
    default_message = "凭据解密失败，加密密钥可能已更换"


# --------------------------------------------------------------------------- 内部错误
class InternalError(AIInsightHubException):
    code = ErrorCode.INTERNAL_ERROR
    default_message = "Internal server error"


__all__ = [
    "AIInsightHubException",
    "ApiKeyInvalidError",
    "ApiKeyNotFoundError",
    "ApiKeyScopeDeniedError",
    "AuthenticationError",
    "CleanedDataNotFoundError",
    "DataSourceNotFoundError",
    "DataSourceQuotaExceededError",
    "FaqNotFoundError",
    "FileFormatInvalidError",
    "FileTooLargeError",
    "InsufficientCreditsError",
    "InternalError",
    "LLMCredentialDecryptError",
    "LLMCredentialInvalidError",
    "LLMCredentialNotConfiguredError",
    "PermissionDeniedError",
    "RateLimitExceededError",
    "RefreshTokenInvalidError",
    "ReportFormatInvalidError",
    "ReportNotFoundError",
    "TaskAlreadyRunningError",
    "TaskNotCancellableError",
    "TaskNotFoundError",
    "TaskNotRetryableError",
    "TokenExpiredError",
    "UserEmailExistsError",
    "UserNotFoundError",
    "WebhookNotFoundError",
]
