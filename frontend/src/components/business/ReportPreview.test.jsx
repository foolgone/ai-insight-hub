import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportPreview } from './ReportPreview'

const REPORT = {
  id: 'r-1',
  title: '质量分析报告-20261025',
  report_type: 'quality',
  format: 'markdown',
  status: 'completed',
  file_size: 2048,
  created_at: '2026-10-25T10:00:00Z',
}

describe('ReportPreview', () => {
  it('展示标题/类型/格式/状态与操作', () => {
    const onPreview = vi.fn()
    const onDownload = vi.fn()
    render(
      <ReportPreview
        report={REPORT}
        onPreview={onPreview}
        onDownload={onDownload}
        onDelete={() => {}}
      />
    )

    expect(screen.getByRole('heading', { name: REPORT.title })).toBeInTheDocument()
    expect(screen.getByText('质量分析')).toBeInTheDocument()
    expect(screen.getByText('MARKDOWN')).toBeInTheDocument()
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '预览' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '下载' })).toBeInTheDocument()
  })

  it('点击预览/下载回调', async () => {
    const onPreview = vi.fn()
    const onDownload = vi.fn()
    const user = userEvent.setup()
    render(<ReportPreview report={REPORT} onPreview={onPreview} onDownload={onDownload} />)

    await user.click(screen.getByRole('button', { name: '预览' }))
    await user.click(screen.getByRole('button', { name: '下载' }))

    expect(onPreview).toHaveBeenCalledWith(REPORT)
    expect(onDownload).toHaveBeenCalledWith(REPORT)
  })

  it('删除走二次确认', async () => {
    const onDelete = vi.fn()
    const user = userEvent.setup()
    render(<ReportPreview report={REPORT} onDelete={onDelete} />)

    await user.click(screen.getByRole('button', { name: '删除' }))
    await user.click(await screen.findByRole('button', { name: '确认' }))

    expect(onDelete).toHaveBeenCalledWith(REPORT)
  })

  it('生成中的报告不展示预览/下载', () => {
    render(
      <ReportPreview
        report={{ ...REPORT, status: 'running' }}
        onPreview={() => {}}
        onDownload={() => {}}
      />
    )

    expect(screen.getByText('生成中')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '预览' })).toBeNull()
    expect(screen.queryByRole('button', { name: '下载' })).toBeNull()
  })
})
