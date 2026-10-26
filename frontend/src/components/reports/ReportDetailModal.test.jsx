import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReportDetailModal } from './ReportDetailModal'
import { downloadReport, getReport } from '../../api/reports'

vi.mock('../../api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

function renderModal() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ReportDetailModal open onClose={() => {}} report={{ id: 'r-1', title: '质量分析报告' }} />
    </QueryClientProvider>
  )
}

describe('ReportDetailModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getReport.mockResolvedValue({
      id: 'r-1',
      title: '质量分析报告',
      report_type: 'quality',
      format: 'markdown',
      status: 'completed',
      created_at: '2026-10-25T10:00:00Z',
      completed_at: '2026-10-25T10:01:00Z',
    })
    downloadReport.mockResolvedValue({ text: async () => '# 报告\n\n这是报告正文。' })
  })

  it('markdown 报告渲染内容', async () => {
    renderModal()

    expect(await screen.findByRole('heading', { name: '报告' })).toBeInTheDocument()
    expect(screen.getByText('这是报告正文。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '下载' })).toBeInTheDocument()
  })

  it('excel 报告仅提示下载', async () => {
    getReport.mockResolvedValue({
      id: 'r-1',
      title: 'Excel 报告',
      report_type: 'quality',
      format: 'excel',
      status: 'completed',
    })
    renderModal()

    expect(
      await screen.findByText('Excel 报告不提供在线预览，请点击「下载」查看。')
    ).toBeInTheDocument()
  })

  it('PDF 报告仅提示下载', async () => {
    getReport.mockResolvedValue({
      id: 'r-1',
      title: 'PDF 报告',
      report_type: 'quality',
      format: 'pdf',
      status: 'completed',
    })
    renderModal()

    expect(
      await screen.findByText('PDF 报告不提供在线预览，请点击「下载」查看。')
    ).toBeInTheDocument()
  })

  it('生成中报告不可下载', async () => {
    getReport.mockResolvedValue({
      id: 'r-1',
      title: '生成中的报告',
      report_type: 'quality',
      format: 'markdown',
      status: 'running',
    })
    renderModal()

    expect((await screen.findAllByText(/生成中/)).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: '下载' })).toBeNull()
  })
})
