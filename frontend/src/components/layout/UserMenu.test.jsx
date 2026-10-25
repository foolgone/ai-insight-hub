import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { UserMenu } from './UserMenu'
import { logout as logoutApi } from '../../api/auth'
import { clearAuth } from '../../lib/authStorage'
import { useAuthStore } from '../../stores/authStore'

vi.mock('../../api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

const ADMIN = { id: 'u1', email: 'admin@example.com', name: '张三', role: 'admin' }

function renderMenu() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<UserMenu />} />
        <Route path="/login" element={<div>login-page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('UserMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearAuth()
    useAuthStore.setState({ user: ADMIN, remember: true })
  })

  afterEach(() => {
    clearAuth()
    useAuthStore.setState({ user: null, remember: false })
  })

  it('展示用户信息与角色', async () => {
    const user = userEvent.setup()
    renderMenu()

    await user.click(screen.getByRole('button', { name: '打开用户菜单' }))

    expect(await screen.findByText('管理员')).toBeInTheDocument()
    expect(screen.getAllByText('admin@example.com').length).toBeGreaterThan(0)
  })

  it('退出登录调用接口并清空会话、跳转登录页', async () => {
    logoutApi.mockResolvedValue({ message: 'ok' })
    const user = userEvent.setup()
    renderMenu()

    await user.click(screen.getByRole('button', { name: '打开用户菜单' }))
    await user.click(await screen.findByRole('menuitem', { name: '退出登录' }))

    expect(await screen.findByText('login-page')).toBeInTheDocument()
    expect(logoutApi).toHaveBeenCalledTimes(1)
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('未登录时不渲染', () => {
    useAuthStore.setState({ user: null })
    const { container } = renderMenu()

    expect(container).toBeEmptyDOMElement()
  })
})
