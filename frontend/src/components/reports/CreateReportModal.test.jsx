import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CreateReportModal } from './CreateReportModal'
import { createReport } from '../../api/reports'

vi.mock('../../api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

function renderModal(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateReportModal open onClose={() => {}} datasourceId="ds-1" {...props} />
    </QueryClientProvider>
  )
}

describe('CreateReportModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createReport.mockResolvedValue({ id: 'r-1' })
  })

  it('默认质量报告 + markdown 并提交 config', async () => {
    const user = userEvent.setup()
    renderModal()

    expect(screen.getByLabelText('标题').value).toMatch(/质量分析报告-\d{8}/)

    await user.click(screen.getByRole('button', { name: '生成报告' }))

    await waitFor(() =>
      expect(createReport).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({
          report_type: 'quality',
          format: 'markdown',
          config: { include_charts: true, include_recommendations: true },
        })
      )
    )
  })

  it('选择 Excel 格式后提交', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('radio', { name: 'Excel' }))
    await user.click(screen.getByRole('button', { name: '生成报告' }))

    await waitFor(() =>
      expect(createReport).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({ format: 'excel' })
      )
    )
  })

  it('选择 PDF 格式后提交', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('radio', { name: 'PDF' }))
    await user.click(screen.getByRole('button', { name: '生成报告' }))

    await waitFor(() =>
      expect(createReport).toHaveBeenCalledWith('ds-1', expect.objectContaining({ format: 'pdf' }))
    )
  })

  it('无数据源时提示', async () => {
    const user = userEvent.setup()
    renderModal({ datasourceId: null })

    await user.click(screen.getByRole('button', { name: '生成报告' }))

    expect(screen.getByRole('alert')).toHaveTextContent('请先选择数据源')
    expect(createReport).not.toHaveBeenCalled()
  })
})
