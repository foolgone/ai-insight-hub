/**
 * Sentry 错误追踪（T7）。
 *
 * - `VITE_SENTRY_DSN` 为空时**完全 no-op**（本地/测试不产生网络请求）；
 * - 用动态 import，未启用时 `@sentry/react` 不进主包；
 * - 上报失败绝不影响业务（捕获后忽略）。
 */
let sdk = null
let initializing = null

/**
 * 初始化 Sentry（幂等）。
 * @returns {Promise<boolean>} 是否启用
 */
export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return Promise.resolve(false)
  if (initializing) return initializing
  initializing = import('@sentry/react')
    .then(Sentry => {
      Sentry.init({
        dsn,
        environment: import.meta.env.VITE_ENVIRONMENT || 'development',
        tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || 0),
      })
      sdk = Sentry
      return true
    })
    .catch(() => false)
  return initializing
}

/**
 * 上报异常（未启用时静默跳过）。
 * @param {unknown} error
 * @param {Object} [extra]
 */
export function captureException(error, extra) {
  if (!sdk) return
  try {
    sdk.captureException(error, extra ? { extra } : undefined)
  } catch {
    // 可观测失败不能影响主流程
  }
}
