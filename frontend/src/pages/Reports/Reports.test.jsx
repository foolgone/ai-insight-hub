import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Reports from './index'
import { deleteReport, downloadReport, getReport, listReports } from '../../api/reports'
import { useDatasourceStore } from '../../stores/datasourceStore'

vi.mock('../../api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

const REPORT = {
  id: 'r-1',
  title: '质量分析报告-20261025',
  report_type: 'quality',
  format: 'markdown',
  status: 'completed',
  file_size: 1024,
  created_at: '2026-10-25T10:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Reports />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasourceStore.setState({ currentId: 'ds-1' })
    listReports.mockResolvedValue({
      items: [REPORT],
      pagination: { page: 1, limit: 9, total: 1, pages: 1 },
    })
    getReport.mockResolvedValue({
      ...REPORT,
      completed_at: '2026-10-25T10:01:00Z',
    })
    downloadReport.mockResolvedValue({ text: async () => '# 报告\n\n正文内容' })
    deleteReport.mockResolvedValue({})
  })

  afterEach(() => useDatasourceStore.setState({ currentId: null }))

  it('渲染报告卡片与操作', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: '报告中心' })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: '质量分析报告-20261025' })
    ).toBeInTheDocument()
    expect(screen.getAllByText('质量分析').length).toBeGreaterThan(0)
    expect(screen.getByText('已完成')).toBeInTheDocument()
  })

  it('打开生成报告弹窗', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '质量分析报告-20261025' })

    await user.click(screen.getByRole('button', { name: '生成报告' }))

    expect(await screen.findByRole('dialog', { name: '生成报告' })).toBeInTheDocument()
  })

  it('预览 markdown 报告', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '质量分析报告-20261025' })

    await user.click(screen.getByRole('button', { name: '预览' }))

    expect(await screen.findByText('正文内容')).toBeInTheDocument()
  })

  it('删除报告走二次确认', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '质量分析报告-20261025' })

    await user.click(screen.getByRole('button', { name: '删除' }))
    await user.click(await screen.findByRole('button', { name: '确认' }))

    await waitFor(() => expect(deleteReport).toHaveBeenCalledWith('r-1'))
  })

  it('未选择数据源时展示引导', async () => {
    useDatasourceStore.setState({ currentId: null })
    renderPage()

    expect(await screen.findByText('尚未选择数据源')).toBeInTheDocument()
    expect(listReports).not.toHaveBeenCalled()
  })
})
