import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DataSources from './index'
import { listDataSources } from '../../api/datasources'
import { useAuthStore } from '../../stores/authStore'

const ADMIN = { id: 'u1', email: 'a@example.com', name: '管理员', role: 'admin' }
const VIEWER = { id: 'u2', email: 'v@example.com', name: '访客', role: 'viewer' }

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

const ITEMS = [
  {
    id: 'ds-1',
    name: '客服对话-1月',
    type: 'customer_service',
    status: 'active',
    statistics: { total_records: 100, cleaned_records: 90, quality_score_avg: 85 },
  },
  {
    id: 'ds-2',
    name: '销售话术-2月',
    type: 'sales',
    status: 'processing',
    statistics: { total_records: 50, cleaned_records: 0, quality_score_avg: 0 },
  },
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/data-sources']}>
        <DataSources />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DataSourcesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    listDataSources.mockResolvedValue({
      items: ITEMS,
      pagination: { page: 1, limit: 20, total: 2, pages: 1 },
    })
  })

  afterEach(() => {
    localStorage.clear()
    useAuthStore.setState({ user: null })
  })

  it('加载后渲染数据源卡片', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: '客服对话-1月' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '销售话术-2月' })).toBeInTheDocument()
    expect(screen.getByText('共 2 条')).toBeInTheDocument()
  })

  it('空列表展示引导', async () => {
    listDataSources.mockResolvedValue({
      items: [],
      pagination: { page: 1, limit: 20, total: 0, pages: 0 },
    })
    renderPage()

    expect(await screen.findByText('暂无数据源，先创建一个吧')).toBeInTheDocument()
  })

  it('当前页搜索过滤卡片', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '客服对话-1月' })

    await user.type(screen.getByLabelText('搜索数据源名称'), '销售')

    expect(screen.getByRole('heading', { name: '销售话术-2月' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '客服对话-1月' })).toBeNull()
  })

  it('点击新建打开 Drawer', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '客服对话-1月' })

    await user.click(screen.getByRole('button', { name: '新建数据源' }))

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '新建数据源' })).toBeInTheDocument()
  })

  it('加载失败展示错误与重试', async () => {
    listDataSources.mockRejectedValue({ status: 500, code: 'INTERNAL_ERROR' })
    renderPage()

    expect(await screen.findByText('服务器异常，请稍后重试')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument()
  })

  it('分页下一页重新请求', async () => {
    listDataSources.mockResolvedValue({
      items: ITEMS,
      pagination: { page: 1, limit: 20, total: 45, pages: 3 },
    })
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '客服对话-1月' })

    await user.click(screen.getByRole('button', { name: '下一页' }))

    await waitFor(() =>
      expect(listDataSources).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2, limit: 20 })
      )
    )
  })

  it('管理员可打开详情与编辑', async () => {
    useAuthStore.setState({ user: ADMIN })
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '客服对话-1月' })

    await user.click(screen.getByRole('button', { name: '数据源操作：客服对话-1月' }))
    await user.click(await screen.findByRole('menuitem', { name: /查看详情/ }))

    expect(await screen.findByRole('dialog', { name: '数据源详情' })).toBeInTheDocument()
  })

  it('viewer 只能查看，不能编辑/删除', async () => {
    useAuthStore.setState({ user: VIEWER })
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '客服对话-1月' })

    await user.click(screen.getByRole('button', { name: '数据源操作：客服对话-1月' }))

    expect(await screen.findByRole('menuitem', { name: /查看详情/ })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /编辑信息/ })).toBeNull()
    expect(screen.queryByRole('menuitem', { name: /删除数据源/ })).toBeNull()
  })
})
