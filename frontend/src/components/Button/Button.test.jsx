import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from './Button'

describe('Button', () => {
  it('渲染子节点，默认 type=button', () => {
    render(<Button>保存</Button>)

    const button = screen.getByRole('button', { name: '保存' })
    expect(button).toBeInTheDocument()
    expect(button).toHaveAttribute('type', 'button')
  })

  it('默认 primary 变体与 md 尺寸', () => {
    render(<Button>确定</Button>)

    const button = screen.getByRole('button', { name: '确定' })
    expect(button).toHaveClass('bg-primary-500')
    expect(button).toHaveClass('h-10')
  })

  it.each([
    ['secondary', 'bg-gray-100'],
    ['outline', 'border-gray-300'],
    ['ghost', 'text-gray-600'],
    ['danger', 'bg-error-500'],
  ])('variant=%s 应用对应样式', (variant, className) => {
    render(<Button variant={variant}>按钮</Button>)

    expect(screen.getByRole('button')).toHaveClass(className)
  })

  it('点击触发 onClick', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={onClick}>提交</Button>)

    await user.click(screen.getByRole('button', { name: '提交' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('disabled 时不触发点击', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button disabled onClick={onClick}>
        禁用
      </Button>
    )

    await user.click(screen.getByRole('button', { name: '禁用' }))

    expect(onClick).not.toHaveBeenCalled()
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('loading 时禁用并暴露 aria-busy', () => {
    render(<Button loading>处理中</Button>)

    const button = screen.getByRole('button', { name: '处理中' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })

  it('支持 icon/iconRight 与 fullWidth', () => {
    render(
      <Button fullWidth icon={<span data-testid="left-icon" />} iconRight={<span />}>
        带图标
      </Button>
    )

    expect(screen.getByTestId('left-icon')).toBeInTheDocument()
    expect(screen.getByRole('button')).toHaveClass('w-full')
  })
})
