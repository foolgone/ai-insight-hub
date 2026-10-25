import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Markdown } from './Markdown'

describe('Markdown', () => {
  it('渲染标题、列表、表格与链接', () => {
    render(
      <Markdown>
        {
          '# 标题\n\n- 项目一\n- 项目二\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n[链接](https://example.com)'
        }
      </Markdown>
    )

    expect(screen.getByRole('heading', { name: '标题' })).toBeInTheDocument()
    expect(screen.getByText('项目一')).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '链接' })).toHaveAttribute('target', '_blank')
  })

  it('禁用原始 HTML（skipHtml）', () => {
    const { container } = render(<Markdown>{'<script>alert(1)</script>\n\n**加粗**'}</Markdown>)

    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText('加粗')).toBeInTheDocument()
  })

  it('空内容不报错', () => {
    const { container } = render(<Markdown>{null}</Markdown>)

    expect(container).toBeInTheDocument()
  })
})
