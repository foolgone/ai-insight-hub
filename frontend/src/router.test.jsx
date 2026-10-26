import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { AppRoutes } from './router'
import { preloadRoutes, renderWithProviders } from './test/utils'
import { useAuthStore } from './stores/authStore'
import { listDataSources } from './api/datasources'
import { listTasks } from './api/tasks'
import { listCleanedData } from './api/cleaning'
import { listQualityResults } from './api/quality'
import { listFaq } from './api/knowledge'
import { listReports } from './api/reports'

vi.mock('./api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))
vi.mock('./api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  retryTask: vi.fn(),
}))
vi.mock('./api/cleaning', () => ({
  startCleaning: vi.fn(),
  listCleanedData: vi.fn(),
  getCleanedData: vi.fn(),
}))
vi.mock('./api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))
vi.mock('./api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))
vi.mock('./api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

const USER = { id: 'u1', email: 'a@example.com', name: '用户', role: 'user' }

// 预热路由懒加载模块，避免全量并行跑时首页偶发停在 Suspense fallback
beforeAll(preloadRoutes, 30000)

function renderAt(path) {
  return renderWithProviders(<AppRoutes />, { route: path })
}

describe('AppRoutes', () => {
  beforeEach(() => {
    listDataSources.mockResolvedValue({
      items: [],
      pagination: { page: 1, limit: 100, total: 0, pages: 0 },
    })
    listTasks.mockResolvedValue({ items: [], pagination: { total: 0 } })
    listCleanedData.mockResolvedValue({ items: [], pagination: { total: 0 } })
    listQualityResults.mockResolvedValue({
      items: [],
      pagination: { total: 0 },
      summary: { total: 0, avg_overall_score: 0, needs_review_count: 0 },
    })
    listFaq.mockResolvedValue({ items: [], pagination: { total: 0 } })
    listReports.mockResolvedValue({ items: [], pagination: { total: 0 } })
  })

  afterEach(() => useAuthStore.setState({ user: null }))

  it('已登录访问 /dashboard 渲染布局与页面', async () => {
    useAuthStore.setState({ user: USER })
    renderAt('/dashboard')

    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }, { timeout: 10000 })
    ).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '主菜单' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '面包屑' })).toHaveTextContent('Dashboard')
  })

  it('未知路由渲染 404', async () => {
    useAuthStore.setState({ user: USER })
    renderAt('/no-such-page')

    expect(await screen.findByRole('heading', { name: '页面不存在' })).toBeInTheDocument()
  })

  it('未登录访问 /login 渲染登录页', async () => {
    useAuthStore.setState({ user: null })
    renderAt('/login')

    expect(
      await screen.findByRole('heading', { name: '欢迎使用 AI Insight Hub' })
    ).toBeInTheDocument()
  })

  it('已登录访问 /login 重定向到 Dashboard', async () => {
    useAuthStore.setState({ user: USER })
    renderAt('/login')

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it.each([
    ['/data-sources', '数据源管理'],
    ['/data-cleaning', '数据清洗'],
    ['/quality-assessment', '质量评估'],
    ['/quality-assessment/abc', '评估详情'],
    ['/knowledge-base', '知识库'],
    ['/reports', '报告中心'],
  ])('已登录访问 %s 渲染 %s 页面', async (path, heading) => {
    useAuthStore.setState({ user: USER })
    renderAt(path)

    expect(
      await screen.findByRole('heading', { name: heading }, { timeout: 5000 })
    ).toBeInTheDocument()
  })
})
