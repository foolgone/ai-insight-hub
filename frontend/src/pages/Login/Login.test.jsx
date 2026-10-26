import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Login from './index'
import { login as loginApi } from '../../api/auth'
import { clearAuth } from '../../lib/authStorage'
import { clearAccessToken } from '../../lib/token'
import { useAuthStore } from '../../stores/authStore'

vi.mock('../../api/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

const USER = { id: 'u1', email: 'user@example.com', name: '用户', role: 'user' }

function renderLogin(path = '/login') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<div>dashboard-page</div>} />
        <Route path="/data-sources" element={<div>datasources-page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

async function fillCredentials(user) {
  await user.type(screen.getByLabelText('邮箱'), 'user@example.com')
  await user.type(screen.getByLabelText('密码'), 'secret-123')
}

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearAuth()
    clearAccessToken()
    useAuthStore.setState({ user: null, remember: false })
  })

  afterEach(() => {
    clearAuth()
    clearAccessToken()
    useAuthStore.setState({ user: null, remember: false })
  })

  it('空表单提交时展示校验错误且不请求登录', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(screen.getByText('请输入邮箱')).toBeInTheDocument()
    expect(screen.getByText('请输入密码')).toBeInTheDocument()
    expect(loginApi).not.toHaveBeenCalled()
  })

  it('登录成功后按 returnUrl 跳转并写入会话', async () => {
    loginApi.mockResolvedValue({
      user: USER,
      access_token: 'access',
    })
    const user = userEvent.setup()
    renderLogin('/login?returnUrl=%2Fdata-sources')

    await fillCredentials(user)
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(loginApi).toHaveBeenCalledWith({
      email: 'user@example.com',
      password: 'secret-123',
    })
    expect(await screen.findByText('datasources-page')).toBeInTheDocument()
    expect(useAuthStore.getState().user).toEqual(USER)
  })

  it('登录失败展示错误文案并保持未登录', async () => {
    loginApi.mockRejectedValue({
      status: 401,
      code: 'AUTH_INVALID_CREDENTIALS',
      message: 'Invalid credentials',
    })
    const user = userEvent.setup()
    renderLogin()

    await fillCredentials(user)
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('邮箱或密码错误')
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('未勾选记住我时只持久化用户信息（不落 token）', async () => {
    loginApi.mockResolvedValue({
      user: USER,
      access_token: 'access',
    })
    const user = userEvent.setup()
    renderLogin()

    await user.click(screen.getByRole('checkbox', { name: '记住我' }))
    await fillCredentials(user)
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByText('dashboard-page')).toBeInTheDocument()
    expect(useAuthStore.getState().remember).toBe(false)
    expect(localStorage.getItem('aiih.auth')).toBeNull()
    // T4：refresh token 在 HttpOnly Cookie，access token 只在内存
    expect(sessionStorage.getItem('aiih.auth')).toContain(USER.email)
    expect(sessionStorage.getItem('aiih.auth')).not.toContain('refresh')
    expect(sessionStorage.getItem('aiih.auth')).not.toContain('access')
  })

  it('提交中禁用按钮并显示登录中', async () => {
    loginApi.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderLogin()

    await fillCredentials(user)
    await user.click(screen.getByRole('button', { name: '登录' }))

    const button = screen.getByRole('button', { name: '登录中...' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByLabelText('邮箱')).toBeDisabled()
  })
})
