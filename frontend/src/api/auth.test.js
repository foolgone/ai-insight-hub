import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient } from './client'
import { fetchCurrentUser, login, logout } from './auth'

const ORIGINAL_ADAPTER = apiClient.defaults.adapter

describe('auth API', () => {
  let lastConfig

  beforeEach(() => {
    lastConfig = null
    apiClient.defaults.adapter = async config => {
      lastConfig = config
      return {
        data: config.method === 'get' ? { id: 'u1' } : { ok: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
  })

  afterEach(() => {
    apiClient.defaults.adapter = ORIGINAL_ADAPTER
  })

  it('login 提交邮箱密码并返回响应体', async () => {
    const result = await login({ email: 'a@example.com', password: 'secret' })

    expect(lastConfig.url).toBe('/auth/login')
    expect(lastConfig.method).toBe('post')
    expect(JSON.parse(lastConfig.data)).toEqual({ email: 'a@example.com', password: 'secret' })
    expect(result).toEqual({ ok: true })
  })

  it('logout 携带 refresh_token', async () => {
    await logout('refresh-token')

    expect(lastConfig.url).toBe('/auth/logout')
    expect(JSON.parse(lastConfig.data)).toEqual({ refresh_token: 'refresh-token' })
  })

  it('logout 无 refresh_token 时提交空对象', async () => {
    await logout()

    expect(JSON.parse(lastConfig.data)).toEqual({})
  })

  it('fetchCurrentUser 请求 /users/me', async () => {
    const result = await fetchCurrentUser()

    expect(lastConfig.url).toBe('/users/me')
    expect(lastConfig.method).toBe('get')
    expect(result).toEqual({ id: 'u1' })
  })
})
