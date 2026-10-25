import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Breadcrumb } from './Breadcrumb'

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Breadcrumb />
    </MemoryRouter>
  )
}

describe('Breadcrumb', () => {
  it('一级页面显示页面名', () => {
    renderAt('/data-sources')
    expect(screen.getByText('数据源管理')).toBeInTheDocument()
    expect(screen.queryByText('详情')).toBeNull()
  })

  it('详情页显示父级链接与「详情」', () => {
    renderAt('/quality-assessment/abc')
    expect(screen.getByRole('link', { name: '质量评估' })).toHaveAttribute(
      'href',
      '/quality-assessment'
    )
    expect(screen.getByText('详情')).toBeInTheDocument()
  })

  it('根路径不渲染面包屑', () => {
    const { container } = renderAt('/')
    expect(container.querySelector('nav')).toBeNull()
  })
})
