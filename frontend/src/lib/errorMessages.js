/** 21 个 MVP 可达业务错误码 → 中文文案（F-105）。 */
const MESSAGES = {
  AUTH_INVALID_CREDENTIALS: '邮箱或密码错误',
  AUTH_TOKEN_EXPIRED: '登录已过期，请重新登录',
  AUTH_REFRESH_TOKEN_INVALID: '登录已失效，请重新登录',
  AUTH_FORBIDDEN: '没有权限执行该操作',
  USER_NOT_FOUND: '用户不存在',
  USER_EMAIL_EXISTS: '该邮箱已注册',
  DATASOURCE_NOT_FOUND: '数据源不存在',
  DATASOURCE_QUOTA_EXCEEDED: '数据源数量已达配额上限',
  CLEANED_DATA_NOT_FOUND: '清洗数据不存在',
  FILE_TOO_LARGE: '文件超过 50MB 限制',
  FILE_FORMAT_INVALID: '文件格式不支持（CSV/JSON/XLSX/TXT）',
  TASK_NOT_FOUND: '任务不存在',
  TASK_ALREADY_RUNNING: '已有同类任务在运行，请稍后再试',
  TASK_NOT_CANCELLABLE: '任务已结束，无法取消',
  TASK_NOT_RETRYABLE: '任务不是失败态，无法重试',
  FAQ_NOT_FOUND: '知识条目不存在',
  REPORT_NOT_FOUND: '报告不存在',
  REPORT_FORMAT_INVALID: '报告类型或格式不受支持',
  INSUFFICIENT_CREDITS: '当日/当月成本额度已用尽',
  RATE_LIMIT_EXCEEDED: '请求过于频繁，请稍后再试',
  LLM_CREDENTIAL_NOT_CONFIGURED: '请先配置自己的 API Key 后再使用 AI 功能',
  LLM_CREDENTIAL_INVALID: 'API Key 无效或已失效，请更新',
  LLM_CREDENTIAL_DECRYPT_FAILED: '凭据解密失败，请联系管理员重新配置',
  INTERNAL_ERROR: '服务器异常，请稍后重试',
}

/** 4 个 Phase 2 错误码（MVP 不触发，保留文案） */
const PHASE2_MESSAGES = {
  API_KEY_NOT_FOUND: 'API Key 不存在',
  API_KEY_INVALID: 'API Key 无效或已吊销',
  API_KEY_SCOPE_DENIED: 'API Key 权限不足',
  WEBHOOK_NOT_FOUND: 'Webhook 配置不存在',
}

/**
 * 把 axios 归一化错误转换成用户可读文案。
 * @param {{ code?: string, status?: number, message?: string, isNetworkError?: boolean }|null|undefined} error
 * @returns {string}
 */
export function getErrorMessage(error) {
  if (!error) return '操作失败，请稍后重试'
  if (error.code && MESSAGES[error.code]) return MESSAGES[error.code]
  if (error.code && PHASE2_MESSAGES[error.code]) return PHASE2_MESSAGES[error.code]

  if (error.isNetworkError) return '网络异常，请检查网络后重试'
  if (error.status === 429) return '请求过于频繁，请稍后再试'
  if (typeof error.status === 'number' && error.status >= 500) {
    return '服务器异常，请稍后重试'
  }
  return error.message || '操作失败，请稍后重试'
}

export const ERROR_MESSAGES = MESSAGES
export const PHASE2_ERROR_MESSAGES = PHASE2_MESSAGES
