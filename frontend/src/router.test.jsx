import { afterEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from './router'
import { useAuthStore } from './stores/authStore'

const USER = { id: 'u1', email: 'a@example.com', name: '用户', role: 'user' }

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>
  )
}

describe('AppRoutes', () => {
  afterEach(() => useAuthStore.setState({ user: null }))

  it('已登录访问 /dashboard 渲染布局与页面', async () => {
    useAuthStore.setState({ user: USER })
    renderAt('/dashboard')

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '主菜单' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '面包屑' })).toHaveTextContent('Dashboard')
  })

  it('未知路由渲染 404', async () => {
    useAuthStore.setState({ user: USER })
    renderAt('/no-such-page')

    expect(await screen.findByRole('heading', { name: '页面不存在' })).toBeInTheDocument()
  })

  it('未登录访问 /login 渲染登录占位页', async () => {
    useAuthStore.setState({ user: null })
    renderAt('/login')

    expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument()
  })

  it('已登录访问 /login 重定向到 Dashboard', async () => {
    useAuthStore.setState({ user: USER })
    renderAt('/login')

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })
})
