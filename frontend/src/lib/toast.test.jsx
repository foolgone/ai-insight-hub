import { afterEach, describe, expect, it } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { notify } from './toast'
import { ToastContainer } from '../components/Toast'

afterEach(() => {
  notify.dismiss()
})

describe('toast', () => {
  it('success 提示可见', async () => {
    render(<ToastContainer />)

    act(() => {
      notify.success('保存成功')
    })

    expect(await screen.findByText('保存成功')).toBeInTheDocument()
  })

  it('error 提示可见', async () => {
    render(<ToastContainer />)

    act(() => {
      notify.error('请求失败')
    })

    expect(await screen.findByText('请求失败')).toBeInTheDocument()
  })

  it('loading 返回 toast id 并可手动关闭', async () => {
    render(<ToastContainer />)
    let toastId = ''

    act(() => {
      toastId = notify.loading('处理中...')
    })

    expect(await screen.findByText('处理中...')).toBeInTheDocument()
    expect(typeof toastId).toBe('string')
    expect(toastId.length).toBeGreaterThan(0)

    act(() => notify.dismiss(toastId))
  })
})
