import { create } from 'zustand'
import { clearAuth, loadAuth, saveAuth } from '../lib/authStorage'
import { clearAccessToken, setAccessToken } from '../lib/token'

/**
 * 认证状态：access_token 只在内存（token.js）；refresh token 在后端 HttpOnly Cookie 中，
 * 前端只按「记住我」持久化用户信息（T4）。
 * @typedef {Object} AuthUser
 * @property {string} id
 * @property {string} email
 * @property {string} name
 * @property {'admin'|'user'|'viewer'} role
 */

export const useAuthStore = create((set, get) => ({
  /** @type {AuthUser|null} */
  user: null,
  remember: false,
  hydrated: false,

  /** 从 Storage 恢复用户信息（应用启动时调用一次；access token 缺失时首个 401 会静默刷新）。 */
  hydrate: () => {
    const saved = loadAuth()
    set({
      user: saved?.user || null,
      remember: saved?.remember || false,
      hydrated: true,
    })
  },

  /**
   * 登录/刷新成功后写入会话。
   * @param {{ user: AuthUser, accessToken: string, remember?: boolean }} session
   */
  setSession: ({ user, accessToken, remember = false }) => {
    if (accessToken) setAccessToken(accessToken)
    saveAuth({ user, remember })
    set({ user, remember, hydrated: true })
  },

  /** 清空内存 + Storage 会话。 */
  clearSession: () => {
    clearAccessToken()
    clearAuth()
    set({ user: null, remember: false })
  },

  /** @returns {boolean} */
  isAuthenticated: () => Boolean(get().user),
}))
