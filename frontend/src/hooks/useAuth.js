import { useCallback } from 'react'
import * as authApi from '../api/auth'
import { loadAuth } from '../lib/authStorage'
import { useAuthStore } from '../stores/authStore'

/**
 * 认证动作（F-103/F-104）：登录写会话，登出清会话。
 * @returns {{
 *   user: Object|null,
 *   remember: boolean,
 *   isAuthenticated: boolean,
 *   login: (params: { email: string, password: string, remember?: boolean }) => Promise<Object>,
 *   logout: () => Promise<void>,
 * }}
 */
export function useAuth() {
  const user = useAuthStore(state => state.user)
  const remember = useAuthStore(state => state.remember)
  const setSession = useAuthStore(state => state.setSession)
  const clearSession = useAuthStore(state => state.clearSession)

  const login = useCallback(
    async ({ email, password, remember: rememberMe = false }) => {
      const data = await authApi.login({ email, password })
      setSession({
        user: data.user,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        remember: rememberMe,
      })
      return data.user
    },
    [setSession]
  )

  const logout = useCallback(async () => {
    const saved = loadAuth()
    try {
      await authApi.logout(saved?.refreshToken)
    } catch {
      // 登出接口失败不阻塞本地清理（token 可能已过期）
    }
    clearSession()
  }, [clearSession])

  return {
    user,
    remember,
    isAuthenticated: Boolean(user),
    login,
    logout,
  }
}
