import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useUiStore } from '../../stores/uiStore'

const ORIGINAL_MATCH_MEDIA = window.matchMedia

function mockMatchMedia(matcher) {
  window.matchMedia = vi.fn().mockImplementation(query => ({
    matches: typeof matcher === 'function' ? matcher(query) : matcher,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

function renderSidebar(path = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>
  )
}

describe('Sidebar', () => {
  beforeEach(() => {
    localStorage.clear()
    useUiStore.setState({ sidebarCollapsed: false, mobileSidebarOpen: false })
  })

  afterEach(() => {
    window.matchMedia = ORIGINAL_MATCH_MEDIA
    useUiStore.setState({ sidebarCollapsed: false, mobileSidebarOpen: false })
  })

  it('渲染 6 个一级菜单与导航语义', () => {
    mockMatchMedia(false)
    renderSidebar()

    expect(screen.getByRole('navigation', { name: '主菜单' })).toBeInTheDocument()
    for (const label of ['Dashboard', '数据源管理', '数据清洗', '质量评估', '知识库', '报告中心']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('折叠后隐藏文字并切换按钮语义', async () => {
    mockMatchMedia(false)
    renderSidebar()

    await userEvent.click(screen.getByRole('button', { name: '折叠侧边栏' }))

    expect(useUiStore.getState().sidebarCollapsed).toBe(true)
    expect(screen.queryByText('数据源管理')).toBeNull()
    expect(screen.getByRole('button', { name: '展开侧边栏' })).toBeInTheDocument()
  })

  it('移动端抽屉可关闭', () => {
    mockMatchMedia(query => query === '(max-width: 767px)')
    renderSidebar()
    act(() => {
      useUiStore.setState({ mobileSidebarOpen: true })
    })

    fireEvent.click(screen.getByRole('button', { name: '关闭菜单' }))

    expect(useUiStore.getState().mobileSidebarOpen).toBe(false)
  })
})
