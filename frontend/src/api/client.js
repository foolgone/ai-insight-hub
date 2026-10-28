import axios from 'axios'
import { API_PREFIX, endpoints } from './endpoints'
import { getAccessToken, setAccessToken } from '../lib/token'
import { clearAuth, loadAuth } from '../lib/authStorage'
import { openCredentialModal } from '../lib/credentialGate'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || API_PREFIX

/** 401 且 refresh 失败后的默认行为（测试可替换）。 */
let unauthorizedHandler = () => {
  if (typeof window === 'undefined') return
  const { pathname, search } = window.location
  if (pathname === '/login') return
  const returnUrl = encodeURIComponent(`${pathname}${search}`)
  window.location.assign(`/login?returnUrl=${returnUrl}`)
}

/**
 * 替换未授权处理器（测试/嵌入式场景用）。
 * @param {() => void} handler
 */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === 'function' ? handler : () => {}
}

export const apiClient = axios.create({ baseURL: BASE_URL, timeout: 30000 })
/** 刷新令牌专用实例：不挂拦截器，避免 401 递归；refresh token 在 HttpOnly Cookie 里。 */
export const refreshClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  withCredentials: true,
})

let refreshPromise = null

/**
 * 用 HttpOnly Cookie 中的 refresh token 换取新 access token（Cookie 由浏览器自动携带）。
 * @returns {Promise<string>} 新 access_token
 */
async function refreshSession() {
  const { data } = await refreshClient.post(endpoints.auth.refresh, {})
  setAccessToken(data.access_token)
  return data.access_token
}

/**
 * 把 axios 异常归一化为前端错误结构（A-2）。
 * @param {any} error
 * @returns {{ status: number, code: string, message: string, details: any, retryAfter: number|null, rateLimitReset: number|null, isNetworkError: boolean }}
 */
export function normalizeError(error) {
  const response = error?.response
  const status = response?.status || 0
  const payload = response?.data
  const apiError = payload && typeof payload === 'object' ? payload.error : null
  const headers = response?.headers || {}
  const retryAfter = Number(headers['retry-after'] || headers['Retry-After']) || null
  const rateLimitReset =
    Number(headers['x-ratelimit-reset'] || headers['X-RateLimit-Reset']) || null

  return {
    status,
    code: apiError?.code || (status ? `HTTP_${status}` : 'NETWORK_ERROR'),
    message: apiError?.message || error?.message || '网络异常，请稍后重试',
    details: apiError?.details ?? null,
    retryAfter,
    rateLimitReset,
    isNetworkError: !response,
  }
}

apiClient.interceptors.request.use(config => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  response => response,
  async error => {
    const original = error?.config
    const status = error?.response?.status
    const isRefreshRequest = original?.url?.includes(endpoints.auth.refresh)

    if (status === 401 && original && !original._retry && !isRefreshRequest) {
      original._retry = true
      const hasSession = Boolean(loadAuth()?.user)

      if (hasSession) {
        try {
          if (!refreshPromise) {
            refreshPromise = refreshSession().finally(() => {
              refreshPromise = null
            })
          }
          const token = await refreshPromise
          original.headers = { ...(original.headers || {}), Authorization: `Bearer ${token}` }
          return apiClient(original)
        } catch {
          clearAuth()
          setAccessToken(null)
          unauthorizedHandler()
          return Promise.reject(normalizeError(error))
        }
      }

      clearAuth()
      setAccessToken(null)
      unauthorizedHandler()
    }

    const normalized = normalizeError(error)
    // BYOK：未配置 Key 触发 AI 操作 → 全局打开凭据设置弹窗（D11）
    if (normalized.code === 'LLM_CREDENTIAL_NOT_CONFIGURED') {
      openCredentialModal()
    }
    return Promise.reject(normalized)
  }
)
