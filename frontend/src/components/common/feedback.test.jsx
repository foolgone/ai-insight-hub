import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ErrorBoundary } from './ErrorBoundary'
import { AsyncState } from './AsyncState'
import { getErrorMessage } from '../../lib/errorMessages'

function Boom() {
  throw new Error('boom')
}

describe('getErrorMessage', () => {
  it('按业务错误码返回中文文案', () => {
    expect(getErrorMessage({ code: 'AUTH_INVALID_CREDENTIALS' })).toBe('邮箱或密码错误')
    expect(getErrorMessage({ code: 'TASK_ALREADY_RUNNING' })).toBe('已有同类任务在运行，请稍后再试')
    expect(getErrorMessage({ code: 'DATASOURCE_QUOTA_EXCEEDED' })).toBe('数据源数量已达配额上限')
  })

  it('Phase 2 错误码也有文案', () => {
    expect(getErrorMessage({ code: 'API_KEY_INVALID' })).toBe('API Key 无效或已吊销')
  })

  it('未知 429 回退到频率提示', () => {
    expect(getErrorMessage({ status: 429, code: 'UNKNOWN' })).toBe('请求过于频繁，请稍后再试')
  })

  it('5xx 与网络错误回退', () => {
    expect(getErrorMessage({ status: 500 })).toBe('服务器异常，请稍后重试')
    expect(getErrorMessage({ isNetworkError: true })).toBe('网络异常，请检查网络后重试')
  })

  it('无错误信息时给出兜底文案', () => {
    expect(getErrorMessage(null)).toBe('操作失败，请稍后重试')
    expect(getErrorMessage({})).toBe('操作失败，请稍后重试')
  })
})

describe('ErrorBoundary', () => {
  afterEach(() => vi.restoreAllMocks())

  it('捕获渲染异常并展示兜底页', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    )

    expect(screen.getByRole('alert')).toHaveTextContent('页面出错了')
  })
})

describe('AsyncState', () => {
  it('loading 渲染加载态', () => {
    render(<AsyncState loading>内容</AsyncState>)

    expect(screen.getByRole('status')).toHaveTextContent('加载中...')
    expect(screen.queryByText('内容')).toBeNull()
  })

  it('error 渲染错误文案与重试按钮', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    render(
      <AsyncState error={{ code: 'DATASOURCE_NOT_FOUND' }} onRetry={onRetry}>
        内容
      </AsyncState>
    )

    expect(screen.getByRole('alert')).toHaveTextContent('数据源不存在')
    await user.click(screen.getByRole('button', { name: '重试' }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('isEmpty 渲染空态', () => {
    render(
      <AsyncState isEmpty emptyText="暂无评估结果">
        内容
      </AsyncState>
    )

    expect(screen.getByText('暂无评估结果')).toBeInTheDocument()
  })

  it('正常时渲染 children', () => {
    render(<AsyncState>内容</AsyncState>)

    expect(screen.getByText('内容')).toBeInTheDocument()
  })
})
