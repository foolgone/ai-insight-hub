import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { APIKeyModal } from './APIKeyModal'

const saveMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  reset: vi.fn(),
}

const deleteMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  reset: vi.fn(),
}

let statusData = { byok_enabled: true, configured: false }

vi.mock('../../hooks/useLlmCredential', () => ({
  useCredentialStatusQuery: () => ({ data: statusData }),
  useSaveCredential: () => saveMutation,
  useDeleteCredential: () => deleteMutation,
}))

describe('APIKeyModal', () => {
  it('未配置时展示输入框与"验证并保存"，无删除按钮', () => {
    statusData = { byok_enabled: true, configured: false }
    render(<APIKeyModal open onClose={() => {}} />)

    expect(screen.getByRole('dialog', { name: '模型 API Key 设置' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('sk-xxxxxxxxxxxxxxxx')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '验证并保存' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: '删除' })).toBeNull()
  })

  it('已配置时展示 key_hint 与删除按钮', () => {
    statusData = {
      byok_enabled: true,
      configured: true,
      key_hint: 'sk-x…a1b2',
      status: 'active',
      verified_at: '2026-10-28T00:00:00Z',
    }
    render(<APIKeyModal open onClose={() => {}} />)

    expect(screen.getByText('sk-x…a1b2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '删除' })).toBeInTheDocument()
  })

  it('demo 用户展示专用提示文案（不含"注册"）', () => {
    statusData = { byok_enabled: true, configured: false }
    render(<APIKeyModal open onClose={() => {}} isDemo />)

    const notice = screen.getByText(/演示账号仅供浏览/)
    expect(notice).toBeInTheDocument()
    expect(notice.textContent).not.toContain('注册')
  })

  it('点击"显示"切换输入框类型', async () => {
    statusData = { byok_enabled: true, configured: false }
    const user = userEvent.setup()
    render(<APIKeyModal open onClose={() => {}} />)

    const input = screen.getByPlaceholderText('sk-xxxxxxxxxxxxxxxx')
    expect(input.type).toBe('password')
    await user.click(screen.getByRole('button', { name: '显示 API Key' }))
    expect(input.type).toBe('text')
  })
})
