import { describe, expect, it } from 'vitest'
import { createQueryClient } from './queryClient'

describe('queryClient', () => {
  it('应用 R-4 默认配置', () => {
    const client = createQueryClient()
    const defaults = client.getDefaultOptions().queries

    expect(defaults.staleTime).toBe(30000)
    expect(defaults.gcTime).toBe(300000)
    expect(defaults.refetchOnWindowFocus).toBe(false)
  })

  it('401/403 不重试，其他错误最多重试一次', () => {
    const retry = createQueryClient().getDefaultOptions().queries.retry

    expect(retry(0, { status: 401 })).toBe(false)
    expect(retry(0, { status: 403 })).toBe(false)
    expect(retry(0, { status: 500 })).toBe(true)
    expect(retry(1, { status: 500 })).toBe(false)
    expect(retry(0, null)).toBe(true)
  })
})
