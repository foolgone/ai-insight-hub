import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QualityAssessment from './index'
import { listQualityResults } from '../../api/quality'
import { useDatasourceStore } from '../../stores/datasourceStore'

vi.mock('../../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))
vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

const RESULT = {
  id: 'q-1',
  data_id: 'cd-1',
  overall_score: 82,
  needs_review: true,
  quality_level: 'good',
  dimensions: {},
  agent_version: 'v1.0.0',
  created_at: '2026-10-24T10:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <QualityAssessment />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('QualityAssessmentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasourceStore.setState({ currentId: 'ds-1' })
    listQualityResults.mockResolvedValue({
      items: [RESULT],
      pagination: { page: 1, limit: 10, total: 1, pages: 1 },
      summary: { total: 1, avg_overall_score: 82, needs_review_count: 1 },
    })
  })

  afterEach(() => useDatasourceStore.setState({ currentId: null }))

  it('展示平均分/待复核、4 档概览与结果行', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: '质量评估' })).toBeInTheDocument()
    expect(await screen.findByText('82.0')).toBeInTheDocument()
    expect(screen.getByText('优秀')).toBeInTheDocument()
    expect(screen.getAllByText('良好').length).toBeGreaterThan(0)
    expect(screen.getByText('合格')).toBeInTheDocument()
    expect(screen.getByText('较差')).toBeInTheDocument()
    expect(screen.getByText('待复核')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看详情' })).toHaveAttribute(
      'href',
      '/quality-assessment/q-1'
    )
  })

  it('打开新建评估任务弹窗', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '质量评估' })

    await user.click(screen.getByRole('button', { name: '新建评估任务' }))

    expect(await screen.findByRole('dialog', { name: '新建评估任务' })).toBeInTheDocument()
  })

  it('未选择数据源时展示引导', async () => {
    useDatasourceStore.setState({ currentId: null })
    renderPage()

    expect(await screen.findByText('尚未选择数据源')).toBeInTheDocument()
    expect(listQualityResults).not.toHaveBeenCalled()
  })
})
