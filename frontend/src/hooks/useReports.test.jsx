import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCreateReport, useDeleteReport, useReportQuery, useReportsQuery } from './useReports'
import { createReport, deleteReport, getReport, listReports } from '../api/reports'

vi.mock('../api/reports', () => ({
  listReports: vi.fn(),
  createReport: vi.fn(),
  getReport: vi.fn(),
  deleteReport: vi.fn(),
  downloadReport: vi.fn(),
}))

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useReports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listReports.mockResolvedValue({ items: [], pagination: { total: 0 } })
    getReport.mockResolvedValue({ id: 'r-1', status: 'completed' })
    createReport.mockResolvedValue({ id: 'r-1' })
    deleteReport.mockResolvedValue({})
  })

  it('列表/详情查询', async () => {
    const disabled = renderHook(() => useReportsQuery(null, {}), { wrapper })
    expect(disabled.result.current.fetchStatus).toBe('idle')

    const list = renderHook(() => useReportsQuery('ds-1', { page: 1 }), { wrapper })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    expect(listReports).toHaveBeenCalledWith('ds-1', { page: 1 })

    const detail = renderHook(() => useReportQuery('r-1'), { wrapper })
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true))
    expect(getReport).toHaveBeenCalledWith('r-1')
  })

  it('生成/删除 mutation', async () => {
    const create = renderHook(() => useCreateReport(), { wrapper })
    await act(() =>
      create.result.current.mutateAsync({
        datasourceId: 'ds-1',
        payload: { title: '报告', report_type: 'quality', format: 'markdown' },
      })
    )
    expect(createReport).toHaveBeenCalledWith('ds-1', {
      title: '报告',
      report_type: 'quality',
      format: 'markdown',
    })

    const remove = renderHook(() => useDeleteReport(), { wrapper })
    await act(() => remove.result.current.mutateAsync('r-1'))
    expect(deleteReport).toHaveBeenCalledWith('r-1')
  })
})
