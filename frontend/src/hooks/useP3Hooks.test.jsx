import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { format, subDays } from 'date-fns'
import { useDashboard } from './useDashboard'
import { useQualityResultsQuery, useReviewQuality, useTriggerQuality } from './useQuality'
import { listDataSources } from '../api/datasources'
import { listTasks } from '../api/tasks'
import { listQualityResults, reviewQuality, triggerQuality } from '../api/quality'
import { listFaq } from '../api/knowledge'
import { listReports } from '../api/reports'

vi.mock('../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))
vi.mock('../api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  retryTask: vi.fn(),
}))
vi.mock('../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))
vi.mock('../api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))
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

const today = format(new Date(), 'yyyy-MM-dd')
const yesterday = format(subDays(new Date(), 1), 'yyyy-MM-dd')

describe('useDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listDataSources.mockResolvedValue({
      items: [{ id: 'ds-1' }, { id: 'ds-2' }, { id: 'ds-3' }],
      pagination: { total: 3 },
    })
    listTasks.mockResolvedValue({
      items: [
        { id: 't1', task_type: 'clean', status: 'completed', created_at: `${today}T10:00:00` },
        { id: 't2', task_type: 'clean', status: 'failed', created_at: `${today}T09:00:00` },
        { id: 't3', task_type: 'clean', status: 'completed', created_at: `${yesterday}T10:00:00` },
        { id: 't4', task_type: 'clean', status: 'completed', created_at: `${yesterday}T09:00:00` },
        { id: 't5', task_type: 'clean', status: 'completed', created_at: `${yesterday}T08:00:00` },
      ],
      pagination: { total: 5 },
    })
    listQualityResults.mockResolvedValue({
      items: [
        { id: 'q1', overall_score: 95 },
        { id: 'q2', overall_score: 80 },
        { id: 'q3', overall_score: 65 },
        { id: 'q4', overall_score: 50 },
      ],
      pagination: { total: 4 },
    })
    listFaq.mockResolvedValue({ items: [], pagination: { total: 7 } })
    listReports.mockResolvedValue({ items: [], pagination: { total: 2 } })
  })

  it('聚合 4 卡、7 天趋势、质量分布与最近任务', async () => {
    const { result } = renderHook(() => useDashboard('ds-1'), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.stats.map(item => item.value)).toEqual([3, 5, 7, 2])
    expect(result.current.qualityDistribution.map(item => item.value)).toEqual([1, 1, 1, 1])
    expect(result.current.trendData).toHaveLength(7)
    expect(result.current.trendData[6].value).toBe(2)
    expect(result.current.recentTasks).toHaveLength(5)
  })

  it('无数据源时知识/报告为 0，质量查询不启用', async () => {
    const { result } = renderHook(() => useDashboard(null), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.stats.map(item => item.value)).toEqual([3, 5, 0, 0])
    expect(listQualityResults).not.toHaveBeenCalled()
    expect(listFaq).not.toHaveBeenCalled()
  })
})

describe('useQuality', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listQualityResults.mockResolvedValue({ items: [], pagination: { total: 0 } })
    triggerQuality.mockResolvedValue({ task_id: 't-1' })
    reviewQuality.mockResolvedValue({ id: 'q-1', decision: 'approved' })
  })

  it('质量列表按数据源启用', async () => {
    const disabled = renderHook(() => useQualityResultsQuery(null, {}), { wrapper })
    expect(disabled.result.current.fetchStatus).toBe('idle')

    const { result } = renderHook(() => useQualityResultsQuery('ds-1', { page: 1 }), {
      wrapper,
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listQualityResults).toHaveBeenCalledWith('ds-1', { page: 1 })
  })

  it('触发评估与复核 mutation', async () => {
    const triggerHook = renderHook(() => useTriggerQuality(), { wrapper })
    await act(() =>
      triggerHook.result.current.mutateAsync({
        datasourceId: 'ds-1',
        dimensions: ['accuracy'],
        threshold: 70,
      })
    )
    expect(triggerQuality).toHaveBeenCalledWith('ds-1', {
      dataIds: undefined,
      dimensions: ['accuracy'],
      threshold: 70,
    })

    const reviewHook = renderHook(() => useReviewQuality(), { wrapper })
    await act(() =>
      reviewHook.result.current.mutateAsync({
        datasourceId: 'ds-1',
        resultId: 'q-1',
        payload: { decision: 'approved' },
      })
    )
    expect(reviewQuality).toHaveBeenCalledWith('ds-1', 'q-1', { decision: 'approved' })
  })
})
