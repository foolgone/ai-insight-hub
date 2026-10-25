import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient, refreshClient, setUnauthorizedHandler } from './client'
import { endpoints } from './endpoints'
import { clearAuth, saveAuth } from '../lib/authStorage'
import { clearAccessToken, setAccessToken } from '../lib/token'

const USER = { id: 'u1', email: 'user@example.com', name: '用户', role: 'user' }

function buildAdapter({ refreshStatus = 200, secureFailures = 1 } = {}) {
  const state = { secureCalls: 0, refreshCalls: 0, tokens: [] }

  const adapter = config => {
    if (config.url === endpoints.auth.refresh) {
      state.refreshCalls += 1
      if (refreshStatus !== 200) {
        return Promise.reject({
          config,
          response: {
            status: refreshStatus,
            data: { error: { code: 'AUTH_REFRESH_TOKEN_INVALID', message: 'refresh 失效' } },
            headers: {},
          },
        })
      }
      return Promise.resolve({
        data: { access_token: 'new-token', refresh_token: 'refresh-2' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      })
    }

    state.secureCalls += 1
    state.tokens.push(config.headers.Authorization || '')
    if (state.secureCalls <= secureFailures) {
      return Promise.reject({
        config,
        response: {
          status: 401,
          data: { error: { code: 'AUTH_TOKEN_EXPIRED', message: 'access 过期' } },
          headers: {},
        },
      })
    }
    return Promise.resolve({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    })
  }

  return { adapter, state }
}

describe('apiClient 401 刷新', () => {
  const originAdapter = apiClient.defaults.adapter
  const originRefreshAdapter = refreshClient.defaults.adapter

  beforeEach(() => {
    clearAuth()
    clearAccessToken()
    setAccessToken('old-token')
    saveAuth({ user: USER, refreshToken: 'refresh-1', remember: true })
  })

  afterEach(() => {
    apiClient.defaults.adapter = originAdapter
    refreshClient.defaults.adapter = originRefreshAdapter
    clearAuth()
    clearAccessToken()
    setUnauthorizedHandler(null)
  })

  it('401 后刷新一次并重放原请求', async () => {
    const { adapter, state } = buildAdapter({ secureFailures: 1 })
    apiClient.defaults.adapter = adapter
    refreshClient.defaults.adapter = adapter

    const response = await apiClient.get('/datasources')

    expect(response.data).toEqual({ ok: true })
    expect(state.refreshCalls).toBe(1)
    expect(state.secureCalls).toBe(2)
    expect(state.tokens[1]).toBe('Bearer new-token')
  })

  it('并发 401 只触发一次刷新（单飞）', async () => {
    const { adapter, state } = buildAdapter({ secureFailures: 2 })
    apiClient.defaults.adapter = adapter
    refreshClient.defaults.adapter = adapter

    const results = await Promise.all([apiClient.get('/datasources'), apiClient.get('/tasks')])

    expect(results).toHaveLength(2)
    expect(state.refreshCalls).toBe(1)
    expect(state.secureCalls).toBe(4)
  })

  it('刷新失败时清会话并调用未授权处理器', async () => {
    const { adapter, state } = buildAdapter({ refreshStatus: 401 })
    const onUnauthorized = vi.fn()
    apiClient.defaults.adapter = adapter
    refreshClient.defaults.adapter = adapter
    setUnauthorizedHandler(onUnauthorized)

    await expect(apiClient.get('/datasources')).rejects.toMatchObject({
      status: 401,
      code: 'AUTH_TOKEN_EXPIRED',
    })

    expect(state.refreshCalls).toBe(1)
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('aiih.auth')).toBeNull()
    expect(sessionStorage.getItem('aiih.auth')).toBeNull()
  })
})
