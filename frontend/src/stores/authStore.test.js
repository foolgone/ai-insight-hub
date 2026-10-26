import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from './authStore'
import { clearAuth } from '../lib/authStorage'
import { clearAccessToken, getAccessToken } from '../lib/token'

const USER = { id: 'u1', email: 'user@example.com', name: '用户', role: 'user' }

function resetStore() {
  useAuthStore.setState({ user: null, remember: false, hydrated: false })
  clearAuth()
  clearAccessToken()
}

describe('authStore', () => {
  beforeEach(resetStore)
  afterEach(resetStore)

  it('setSession 写入内存 token 与持久化会话（记住我 → localStorage）', () => {
    useAuthStore.getState().setSession({
      user: USER,
      accessToken: 'access-1',
      remember: true,
    })

    expect(useAuthStore.getState().user).toEqual(USER)
    expect(useAuthStore.getState().isAuthenticated()).toBe(true)
    expect(getAccessToken()).toBe('access-1')
    expect(JSON.parse(localStorage.getItem('aiih.auth'))).toEqual({
      user: USER,
      remember: true,
    })
    expect(sessionStorage.getItem('aiih.auth')).toBeNull()
    // access / refresh token 都不落 Web Storage（T4：refresh 只在 HttpOnly Cookie）
    expect(localStorage.getItem('aiih.auth')).not.toContain('access-1')
    expect(localStorage.getItem('aiih.auth')).not.toContain('refresh')
  })

  it('未勾选记住我时写 sessionStorage', () => {
    useAuthStore.getState().setSession({
      user: USER,
      accessToken: 'access-2',
      remember: false,
    })

    expect(sessionStorage.getItem('aiih.auth')).toContain(USER.email)
    expect(localStorage.getItem('aiih.auth')).toBeNull()
  })

  it('hydrate 从 Storage 恢复用户', () => {
    useAuthStore.getState().setSession({
      user: USER,
      accessToken: 'access-3',
      remember: true,
    })
    useAuthStore.setState({ user: null, remember: false })

    useAuthStore.getState().hydrate()

    expect(useAuthStore.getState().user).toEqual(USER)
    expect(useAuthStore.getState().remember).toBe(true)
    expect(useAuthStore.getState().hydrated).toBe(true)
  })

  it('clearSession 清空内存与两处 Storage', () => {
    useAuthStore.getState().setSession({
      user: USER,
      accessToken: 'access-4',
      remember: true,
    })

    useAuthStore.getState().clearSession()

    expect(useAuthStore.getState().user).toBeNull()
    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem('aiih.auth')).toBeNull()
    expect(sessionStorage.getItem('aiih.auth')).toBeNull()
  })
})
