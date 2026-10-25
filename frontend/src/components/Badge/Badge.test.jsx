import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from './Badge'

describe('Badge', () => {
  it('渲染文本内容', () => {
    render(<Badge>已就绪</Badge>)

    expect(screen.getByText('已就绪')).toBeInTheDocument()
  })

  it.each([
    ['success', 'bg-success-50'],
    ['warning', 'bg-warning-50'],
    ['error', 'bg-error-50'],
    ['info', 'bg-info-50'],
    ['default', 'bg-gray-100'],
  ])('variant=%s 应用对应背景色', (variant, className) => {
    render(<Badge variant={variant}>标签</Badge>)

    expect(screen.getByText('标签')).toHaveClass(className)
  })

  it('size=sm 使用小号样式', () => {
    render(<Badge size="sm">小</Badge>)

    expect(screen.getByText('小')).toHaveClass('text-xs')
  })

  it('支持追加自定义类名', () => {
    render(<Badge className="ml-2">自定义</Badge>)

    expect(screen.getByText('自定义')).toHaveClass('ml-2')
  })
})
