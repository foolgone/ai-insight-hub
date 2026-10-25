import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal } from './Modal'

describe('Modal', () => {
  it('open 时渲染标题与内容', () => {
    render(
      <Modal open onClose={() => {}} title="确认删除">
        此操作不可恢复
      </Modal>
    )

    expect(screen.getByRole('dialog', { name: '确认删除' })).toBeInTheDocument()
    expect(screen.getByText('此操作不可恢复')).toBeInTheDocument()
  })

  it('点击关闭按钮触发 onClose', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Modal open onClose={onClose} title="提示">
        内容
      </Modal>
    )

    await user.click(screen.getByRole('button', { name: '关闭' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Esc 关闭触发 onClose', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Modal open onClose={onClose} title="提示">
        内容
      </Modal>
    )

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('渲染 footer 操作区', () => {
    render(
      <Modal open onClose={() => {}} title="提示" footer={<button type="button">确定</button>}>
        内容
      </Modal>
    )

    expect(screen.getByRole('button', { name: '确定' })).toBeInTheDocument()
  })

  it('size=xl 使用 1000px 宽度', () => {
    render(
      <Modal open onClose={() => {}} title="大弹窗" size="xl">
        内容
      </Modal>
    )

    expect(screen.getByRole('dialog')).toHaveClass('md:max-w-[1000px]')
  })

  it('closed 时不渲染内容', () => {
    render(
      <Modal open={false} onClose={() => {}} title="隐藏">
        内容
      </Modal>
    )

    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
