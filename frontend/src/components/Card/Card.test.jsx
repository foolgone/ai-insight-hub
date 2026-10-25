import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Card } from './Card'

describe('Card', () => {
  it('渲染标题、操作区与内容', () => {
    render(
      <Card title="质量概览" extra={<button type="button">刷新</button>}>
        内容
      </Card>
    )

    expect(screen.getByRole('heading', { name: '质量概览' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刷新' })).toBeInTheDocument()
    expect(screen.getByText('内容')).toBeInTheDocument()
  })

  it('渲染 footer', () => {
    render(<Card footer="共 12 条">内容</Card>)

    expect(screen.getByText('共 12 条')).toBeInTheDocument()
  })

  it('flat 变体无阴影', () => {
    const { container } = render(<Card variant="flat">内容</Card>)

    expect(container.firstChild).not.toHaveClass('shadow')
    expect(container.firstChild).toHaveClass('shadow-none')
  })

  it('hoverable 时带 hover 阴影', () => {
    const { container } = render(<Card hoverable>内容</Card>)

    expect(container.firstChild).toHaveClass('hover:shadow-md')
  })

  it('loading 时渲染骨架并标记 aria-busy', () => {
    const { container } = render(<Card loading>内容</Card>)

    expect(screen.getByRole('status', { name: '加载中' })).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('aria-busy', 'true')
  })

  it('无标题时只渲染内容区', () => {
    render(<Card>仅内容</Card>)

    expect(screen.queryByRole('heading')).toBeNull()
    expect(screen.getByText('仅内容')).toBeInTheDocument()
  })
})
