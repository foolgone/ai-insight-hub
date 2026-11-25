import { afterEach, describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { usePermissions } from './usePermissions'
import { useAuthStore } from '../stores/authStore'

const ADMIN = { id: 'u1', email: 'a@example.com', name: '管理员', role: 'admin' }
const VIEWER = { id: 'u2', email: 'v@example.com', name: '访客', role: 'viewer' }
const TENANT_ADMIN = { id: 'u3', email: 't@example.com', name: '租户管理员', role: 'tenant_admin' }
const PLATFORM_ADMIN = {
  id: 'u4',
  email: 'p@example.com',
  name: '平台管理员',
  role: 'platform_admin',
}

describe('usePermissions', () => {
  afterEach(() => useAuthStore.setState({ user: null }))

  it('admin 可写且可匹配 admin/user', () => {
    useAuthStore.setState({ user: ADMIN })
    const { result } = renderHook(() => usePermissions())

    expect(result.current.role).toBe('admin')
    expect(result.current.isAdmin).toBe(true)
    expect(result.current.canWrite).toBe(true)
    expect(result.current.can(['admin', 'user'])).toBe(true)
  })

  it('tenant_admin / platform_admin 视为管理员且可写', () => {
    for (const user of [TENANT_ADMIN, PLATFORM_ADMIN]) {
      useAuthStore.setState({ user })
      const { result } = renderHook(() => usePermissions())
      expect(result.current.isAdmin).toBe(true)
      expect(result.current.canWrite).toBe(true)
      expect(result.current.can(['admin', 'user'])).toBe(true)
    }
  })

  it('viewer 只读', () => {
    useAuthStore.setState({ user: VIEWER })
    const { result } = renderHook(() => usePermissions())

    expect(result.current.isViewer).toBe(true)
    expect(result.current.canWrite).toBe(false)
    expect(result.current.can(['admin', 'user'])).toBe(false)
  })
})
