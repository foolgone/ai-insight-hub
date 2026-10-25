import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 登录（POST /auth/login）。
 * @param {{ email: string, password: string }} credentials
 * @returns {Promise<{ user: Object, access_token: string, refresh_token: string, token_type: string, expires_in: number, refresh_expires_in: number }>}
 */
export async function login({ email, password }) {
  const { data } = await apiClient.post(endpoints.auth.login, { email, password })
  return data
}

/**
 * 登出（POST /auth/logout）：同时吊销 access/refresh token。
 * @param {string} [refreshToken]
 * @returns {Promise<{ message: string }>}
 */
export async function logout(refreshToken) {
  const { data } = await apiClient.post(
    endpoints.auth.logout,
    refreshToken ? { refresh_token: refreshToken } : {}
  )
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
