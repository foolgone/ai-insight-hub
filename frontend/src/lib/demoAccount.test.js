import { describe, expect, it } from 'vitest'
import { DEMO_ACCOUNT, isDemoUser } from './demoAccount'

describe('demoAccount', () => {
  it('演示账号常量与需求一致', () => {
    expect(DEMO_ACCOUNT.email).toBe('demo@example.com')
    expect(DEMO_ACCOUNT.password).toBe('demo123')
  })

  it('isDemoUser 按邮箱判断', () => {
    expect(isDemoUser({ email: DEMO_ACCOUNT.email })).toBe(true)
    expect(isDemoUser({ email: 'other@example.com' })).toBe(false)
    expect(isDemoUser(null)).toBe(false)
  })
})
