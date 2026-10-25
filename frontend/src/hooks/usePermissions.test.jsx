import { afterEach, describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { usePermissions } from './usePermissions'
import { useAuthStore } from '../stores/authStore'

const ADMIN = { id: 'u1', email: 'a@example.com', name: '管理员', role: 'admin' }
const VIEWER = { id: 'u2', email: 'v@example.com', name: '访客', role: 'viewer' }

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

  it('viewer 只读', () => {
    useAuthStore.setState({ user: VIEWER })
    const { result } = renderHook(() => usePermissions())

    expect(result.current.isViewer).toBe(true)
    expect(result.current.canWrite).toBe(false)
    expect(result.current.can(['admin', 'user'])).toBe(false)
  })
})
