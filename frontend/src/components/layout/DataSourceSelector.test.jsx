import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DataSourceSelector } from './DataSourceSelector'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { listDataSources } from '../../api/datasources'

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

const ITEMS = [
  { id: 'ds-1', name: '客服对话-1月', status: 'active' },
  { id: 'ds-2', name: '销售话术-2月', status: 'processing' },
]

function renderSelector() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DataSourceSelector />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DataSourceSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useDatasourceStore.setState({ currentId: null })
    listDataSources.mockResolvedValue({
      items: ITEMS,
      pagination: { page: 1, limit: 100, total: 2, pages: 1 },
    })
  })

  afterEach(() => {
    useDatasourceStore.setState({ currentId: null })
  })

  it('加载后默认选中第一个数据源', async () => {
    renderSelector()

    await waitFor(() => expect(useDatasourceStore.getState().currentId).toBe('ds-1'))
    expect(screen.getByRole('button', { name: '数据源选择器' })).toHaveTextContent('客服对话-1月')
  })

  it('打开列表并切换数据源', async () => {
    const user = userEvent.setup()
    renderSelector()
    await waitFor(() => expect(useDatasourceStore.getState().currentId).toBe('ds-1'))

    await user.click(screen.getByRole('button', { name: '数据源选择器' }))
    await user.click(await screen.findByRole('option', { name: /销售话术-2月/ }))

    expect(useDatasourceStore.getState().currentId).toBe('ds-2')
    expect(screen.getByRole('button', { name: '数据源选择器' })).toHaveTextContent('销售话术-2月')
    await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull())
  })

  it('无数据源时展示引导', async () => {
    listDataSources.mockResolvedValue({
      items: [],
      pagination: { page: 1, limit: 100, total: 0, pages: 0 },
    })
    const user = userEvent.setup()
    renderSelector()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '数据源选择器' })).toHaveTextContent('选择数据源')
    )
    await user.click(screen.getByRole('button', { name: '数据源选择器' }))
    expect(await screen.findByText('暂无数据源')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '新建数据源' })).toBeInTheDocument()
  })

  it('加载失败展示重试', async () => {
    listDataSources.mockRejectedValue({ status: 500, code: 'INTERNAL_ERROR' })
    renderSelector()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '数据源选择器' })).toHaveTextContent(
        '数据源加载失败'
      )
    )
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: '数据源选择器' }))
    expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument()
  })
})
