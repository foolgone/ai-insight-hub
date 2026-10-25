import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DataCleaning from './index'
import { cancelTask, listTasks, retryTask } from '../../api/tasks'
import { listCleanedData } from '../../api/cleaning'
import { listDataSources } from '../../api/datasources'
import { useDatasourceStore } from '../../stores/datasourceStore'

vi.mock('../../api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  retryTask: vi.fn(),
}))
vi.mock('../../api/cleaning', () => ({
  startCleaning: vi.fn(),
  listCleanedData: vi.fn(),
  getCleanedData: vi.fn(),
}))
vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

const RUNNING_TASK = {
  id: '12345678-abcd-efgh',
  task_type: 'clean',
  status: 'running',
  progress: 45,
  created_at: '2026-10-24T10:00:00Z',
}
const FAILED_TASK = {
  id: 'failed00-abcd-efgh',
  task_type: 'clean',
  status: 'failed',
  progress: 20,
  created_at: '2026-10-24T09:00:00Z',
}
const CLEANED_ITEM = {
  dialogue_id: 'dlg-1',
  timestamp: '2026-10-24T10:30:00Z',
  user_message: '如何退款？',
  ai_response: '7 天内可无理由退款。',
  quality_score: 88,
  issues: [],
  metadata: null,
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <DataCleaning />
    </QueryClientProvider>
  )
}

describe('DataCleaningPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useDatasourceStore.setState({ currentId: 'ds-1' })
    listTasks.mockResolvedValue({
      items: [RUNNING_TASK, FAILED_TASK],
      pagination: { page: 1, limit: 20, total: 2, pages: 1 },
    })
    listCleanedData.mockResolvedValue({
      items: [CLEANED_ITEM],
      pagination: { page: 1, limit: 10, total: 1, pages: 1 },
    })
    listDataSources.mockResolvedValue({
      items: [{ id: 'ds-1', name: '客服1月' }],
      pagination: { total: 1 },
    })
    cancelTask.mockResolvedValue({ status: 'cancelled' })
    retryTask.mockResolvedValue({ status: 'pending' })
  })

  afterEach(() => {
    useDatasourceStore.setState({ currentId: null })
    localStorage.clear()
  })

  it('渲染 Tabs、任务与清洗结果', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: '数据清洗' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '全部' })).toBeInTheDocument()
    expect(await screen.findByText('12345678')).toBeInTheDocument()
    expect(screen.getAllByText('进行中').length).toBeGreaterThan(0)
    expect(await screen.findByText('如何退款？')).toBeInTheDocument()
    expect(screen.getByText('88.0')).toBeInTheDocument()
  })

  it('取消进行中的任务', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('12345678')

    await user.click(screen.getByRole('button', { name: '取消' }))

    await waitFor(() => expect(cancelTask).toHaveBeenCalledWith(RUNNING_TASK.id, expect.anything()))
  })

  it('重试失败任务', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('failed00')

    await user.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => expect(retryTask).toHaveBeenCalledWith(FAILED_TASK.id, expect.anything()))
  })

  it('切换状态 Tab 重新查询', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('12345678')

    await user.click(screen.getByRole('tab', { name: '失败' }))

    await waitFor(() =>
      expect(listTasks).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'failed', task_type: 'clean' })
      )
    )
  })

  it('未选择数据源时结果区展示引导', async () => {
    useDatasourceStore.setState({ currentId: null })
    renderPage()

    expect(await screen.findByText('尚未选择数据源')).toBeInTheDocument()
    expect(listCleanedData).not.toHaveBeenCalled()
  })

  it('点击查看打开清洗结果详情', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('如何退款？')

    await user.click(screen.getByRole('button', { name: '查看' }))

    expect(await screen.findByRole('dialog', { name: '清洗结果详情' })).toBeInTheDocument()
  })

  it('打开新建清洗任务弹窗', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('12345678')

    await user.click(screen.getByRole('button', { name: '新建清洗任务' }))

    expect(await screen.findByRole('dialog', { name: '新建清洗任务' })).toBeInTheDocument()
  })
})
