import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './index'
import { listDataSources } from '../../api/datasources'
import { listTasks } from '../../api/tasks'
import { listQualityResults } from '../../api/quality'
import { listFaq } from '../../api/knowledge'
import { listReports } from '../../api/reports'
import { useDatasourceStore } from '../../stores/datasourceStore'

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))
vi.mock('../../api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  retryTask: vi.fn(),
}))
vi.mock('../../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))
vi.mock('../../api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))
vi.mock('../../api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasourceStore.setState({ currentId: 'ds-1' })
    listDataSources.mockResolvedValue({
      items: [{ id: 'ds-1' }],
      pagination: { total: 3 },
    })
    listTasks.mockResolvedValue({
      items: [
        {
          id: 'task-1234-abcd',
          task_type: 'clean',
          status: 'completed',
          created_at: new Date().toISOString(),
        },
      ],
      pagination: { total: 9 },
    })
    listQualityResults.mockResolvedValue({
      items: [{ id: 'q1', overall_score: 85 }],
      pagination: { total: 1 },
    })
    listFaq.mockResolvedValue({ items: [], pagination: { total: 7 } })
    listReports.mockResolvedValue({ items: [], pagination: { total: 2 } })
  })

  afterEach(() => useDatasourceStore.setState({ currentId: null }))

  it('渲染 4 张统计卡、趋势图、质量分布与最近任务', async () => {
    renderDashboard()

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByText('数据源')).toBeInTheDocument()
    expect(screen.getByText('清洗任务')).toBeInTheDocument()
    expect(screen.getByText('知识条目')).toBeInTheDocument()
    expect(screen.getByText('报告数')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()

    expect(screen.getByRole('region', { name: '处理量趋势（最近 7 天）' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '质量分布（最近 100 条样本）' })).toBeInTheDocument()
    expect(screen.getByText('task-123')).toBeInTheDocument()
  })

  it('未选择数据源时质量分布显示引导', async () => {
    useDatasourceStore.setState({ currentId: null })
    renderDashboard()

    expect(await screen.findByText('尚未选择数据源')).toBeInTheDocument()
  })
})
