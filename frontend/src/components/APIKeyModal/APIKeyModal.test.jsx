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

const asrSaveMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  reset: vi.fn(),
}

const asrDeleteMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  reset: vi.fn(),
}

let asrStatusData = { asr_enabled: true, configured: false }

vi.mock('../../hooks/useAsrCredential', () => ({
  useAsrCredentialStatusQuery: () => ({ data: asrStatusData }),
  useSaveAsrCredential: () => asrSaveMutation,
  useDeleteAsrCredential: () => asrDeleteMutation,
}))

describe('APIKeyModal', () => {
  it('未配置时展示输入框与"验证并保存"，无删除按钮', () => {
    statusData = { byok_enabled: true, configured: false }
    render(<APIKeyModal open onClose={() => {}} />)

    expect(screen.getByRole('dialog', { name: '模型 API Key 设置' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('sk-xxxxxxxxxxxxxxxx')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '验证并保存' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: '删除 Key' })).toBeNull()
  })

  it('已配置时展示 key_hint 与删除入口', () => {
    statusData = {
      byok_enabled: true,
      configured: true,
      key_hint: 'sk-x…a1b2',
      status: 'active',
      verified_at: '2026-10-28T00:00:00Z',
    }
    render(<APIKeyModal open onClose={() => {}} />)

    expect(screen.getByText('sk-x…a1b2')).toBeInTheDocument()
    expect(screen.getByText(/已加密存储在服务器/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '删除 Key' })).toBeInTheDocument()
  })

  it('删除需要二次确认，确认后调用删除接口', async () => {
    statusData = {
      byok_enabled: true,
      configured: true,
      key_hint: 'sk-x…a1b2',
      status: 'active',
    }
    deleteMutation.mutateAsync.mockResolvedValueOnce(undefined)
    const user = userEvent.setup()
    render(<APIKeyModal open onClose={() => {}} />)

    await user.click(screen.getByRole('button', { name: '删除 Key' }))

    expect(screen.getByText('从服务器删除这个 Key？')).toBeInTheDocument()
    expect(screen.getByText(/服务器上不再保留该 Key/)).toBeInTheDocument()
    expect(deleteMutation.mutateAsync).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '确认删除' }))
    expect(deleteMutation.mutateAsync).toHaveBeenCalledTimes(1)
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

  it('两个标签页：默认模型 API Key，可切到语音转写', async () => {
    statusData = { byok_enabled: true, configured: false }
    asrStatusData = { asr_enabled: true, configured: false }
    const user = userEvent.setup()
    render(<APIKeyModal open onClose={() => {}} />)

    expect(screen.getByRole('tab', { name: '模型 API Key' })).toHaveAttribute(
      'aria-selected',
      'true'
    )

    await user.click(screen.getByRole('tab', { name: '语音转写' }))

    expect(screen.getByRole('dialog', { name: '语音转写设置' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('https://api.siliconflow.cn/v1')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('whisper-1')).toBeInTheDocument()
    expect(screen.getByLabelText('识别语言')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '验证并保存' })).toBeDisabled()
  })

  it('initialTab=asr 时直接打开语音转写页', () => {
    asrStatusData = {
      asr_enabled: true,
      configured: true,
      base_url: 'https://api.siliconflow.cn/v1',
      model: 'FunAudioLLM/SenseVoiceSmall',
      language: 'zh',
      key_hint: 'sk-ab…cdef',
      status: 'active',
    }
    render(<APIKeyModal open onClose={() => {}} initialTab="asr" />)

    expect(screen.getByRole('dialog', { name: '语音转写设置' })).toBeInTheDocument()
    expect(screen.getByText('https://api.siliconflow.cn/v1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '删除配置' })).toBeInTheDocument()
  })

  it('语音转写删除同样需要二次确认', async () => {
    asrStatusData = {
      asr_enabled: true,
      configured: true,
      base_url: 'https://api.siliconflow.cn/v1',
      model: 'whisper-1',
      language: 'zh',
      key_hint: 'sk-ab…cdef',
      status: 'active',
    }
    asrDeleteMutation.mutateAsync.mockClear()
    asrDeleteMutation.mutateAsync.mockResolvedValueOnce(undefined)
    const user = userEvent.setup()
    render(<APIKeyModal open onClose={() => {}} initialTab="asr" />)

    await user.click(screen.getByRole('button', { name: '删除配置' }))

    expect(screen.getByText('从服务器删除语音转写配置？')).toBeInTheDocument()
    expect(asrDeleteMutation.mutateAsync).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '确认删除' }))
    expect(asrDeleteMutation.mutateAsync).toHaveBeenCalledTimes(1)
  })
})
