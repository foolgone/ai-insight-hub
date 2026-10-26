import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 登录（POST /auth/login）。
 * 响应只有 access_token；refresh token 由后端写入 HttpOnly Cookie（T4），前端不可读。
 * @param {{ email: string, password: string }} credentials
 * @returns {Promise<{ user: Object, access_token: string, token_type: string, expires_in: number, refresh_expires_in: number }>}
 */
export async function login({ email, password }) {
  const { data } = await apiClient.post(endpoints.auth.login, { email, password })
  return data
}

/**
 * 登出（POST /auth/logout）：后端吊销 access + Cookie 中的 refresh token 并清除 Cookie。
 * @returns {Promise<{ message: string }>}
 */
export async function logout() {
  const { data } = await apiClient.post(endpoints.auth.logout, {}, { withCredentials: true })
  return data
}

/**
 * 当前用户信息（GET /users/me）。
 * @returns {Promise<{ id: string, email: string, name: string, role: string }>}
 */
export async function fetchCurrentUser() {
  const { data } = await apiClient.get(endpoints.users.me)
  return data
}
