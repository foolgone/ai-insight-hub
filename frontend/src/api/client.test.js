import { describe, expect, it } from 'vitest'
import { normalizeError } from './client'

describe('normalizeError', () => {
  it('解析统一错误体 {error:{code,message,details}}', () => {
    const error = normalizeError({
      response: {
        status: 409,
        data: {
          error: { code: 'TASK_ALREADY_RUNNING', message: '任务运行中', details: { task: 1 } },
        },
        headers: {},
      },
    })

    expect(error.status).toBe(409)
    expect(error.code).toBe('TASK_ALREADY_RUNNING')
    expect(error.message).toBe('任务运行中')
    expect(error.details).toEqual({ task: 1 })
    expect(error.isNetworkError).toBe(false)
  })

  it('非统一错误体时回退到 HTTP_<status>', () => {
    const error = normalizeError({
      response: { status: 500, data: { detail: 'boom' }, headers: {} },
      message: 'Request failed',
    })

    expect(error.code).toBe('HTTP_500')
    expect(error.message).toBe('Request failed')
  })

  it('网络错误无 response 时标记为 NETWORK_ERROR', () => {
    const error = normalizeError({ message: 'Network Error' })

    expect(error.status).toBe(0)
    expect(error.code).toBe('NETWORK_ERROR')
    expect(error.isNetworkError).toBe(true)
  })

  it('读取 429 的 Retry-After 与 X-RateLimit-Reset', () => {
    const error = normalizeError({
      response: {
        status: 429,
        data: { error: { code: 'INSUFFICIENT_CREDITS', message: '额度不足' } },
        headers: { 'retry-after': '30', 'x-ratelimit-reset': '1736945400' },
      },
    })

    expect(error.code).toBe('INSUFFICIENT_CREDITS')
    expect(error.retryAfter).toBe(30)
    expect(error.rateLimitReset).toBe(1736945400)
  })
})
