import { afterEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'
import { PublicOnlyRoute } from './PublicOnlyRoute'
import { RequireRole } from './RequireRole'
import { useAuthStore } from '../../stores/authStore'

const USER = { id: 'u1', email: 'a@example.com', name: '用户', role: 'user' }

function renderGuarded(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<div>dashboard-content</div>} />
        </Route>
        <Route path="/login" element={<div>login-page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute / PublicOnlyRoute', () => {
  afterEach(() => useAuthStore.setState({ user: null }))

  it('未登录访问业务页跳登录', () => {
    useAuthStore.setState({ user: null })
    renderGuarded('/dashboard')

    expect(screen.getByText('login-page')).toBeInTheDocument()
  })

  it('已登录渲染业务页', () => {
    useAuthStore.setState({ user: USER })
    renderGuarded('/dashboard')

    expect(screen.getByText('dashboard-content')).toBeInTheDocument()
  })

  it('已登录访问登录页跳 Dashboard', () => {
    useAuthStore.setState({ user: USER })
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<div>login-page</div>} />
          </Route>
          <Route path="/dashboard" element={<div>dashboard-content</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('dashboard-content')).toBeInTheDocument()
  })
})

describe('RequireRole', () => {
  afterEach(() => useAuthStore.setState({ user: null }))

  it('viewer 显示无权限提示', () => {
    useAuthStore.setState({ user: { ...USER, role: 'viewer' } })
    render(
      <RequireRole roles={['admin']}>
        <div>admin-only</div>
      </RequireRole>
    )

    expect(screen.getByRole('alert')).toHaveTextContent('无权限访问该页面')
    expect(screen.queryByText('admin-only')).toBeNull()
  })

  it('admin 渲染受控内容', () => {
    useAuthStore.setState({ user: { ...USER, role: 'admin' } })
    render(
      <RequireRole roles={['admin']}>
        <div>admin-only</div>
      </RequireRole>
    )

    expect(screen.getByText('admin-only')).toBeInTheDocument()
  })
})
