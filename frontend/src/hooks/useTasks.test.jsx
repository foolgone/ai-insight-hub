import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCancelTask, useRetryTask, useTaskQuery, useTasksQuery } from './useTasks'
import { useCleanedDataDetailQuery, useCleanedDataQuery, useStartCleaning } from './useCleaning'
import { cancelTask, getTask, listTasks, retryTask } from '../api/tasks'
import { getCleanedData, listCleanedData, startCleaning } from '../api/cleaning'

vi.mock('../api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  cancelTask: vi.fn(),
  retryTask: vi.fn(),
}))
vi.mock('../api/cleaning', () => ({
  startCleaning: vi.fn(),
  listCleanedData: vi.fn(),
  getCleanedData: vi.fn(),
}))

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useTasks / useCleaning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTasks.mockResolvedValue({ items: [], pagination: { total: 0 } })
    getTask.mockResolvedValue({ id: 't-1' })
    cancelTask.mockResolvedValue({ status: 'cancelled' })
    retryTask.mockResolvedValue({ status: 'pending' })
    listCleanedData.mockResolvedValue({ items: [], pagination: { total: 0 } })
    getCleanedData.mockResolvedValue({ id: 'cd-1' })
    startCleaning.mockResolvedValue({ task_id: 't-1' })
  })

  it('useTasksQuery 调用任务列表', async () => {
    const { result } = renderHook(() => useTasksQuery({ task_type: 'clean' }), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listTasks).toHaveBeenCalledWith({ task_type: 'clean' })
  })

  it('useTaskQuery 无 id 不请求、有 id 请求详情', async () => {
    const disabled = renderHook(() => useTaskQuery(null), { wrapper })
    expect(disabled.result.current.fetchStatus).toBe('idle')

    const { result } = renderHook(() => useTaskQuery('t-1'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(getTask).toHaveBeenCalledWith('t-1')
  })

  it('取消/重试 mutation 调用 API', async () => {
    const cancelHook = renderHook(() => useCancelTask(), { wrapper })
    await act(() => cancelHook.result.current.mutateAsync('t-1'))
    expect(cancelTask).toHaveBeenCalledWith('t-1', expect.anything())

    const retryHook = renderHook(() => useRetryTask(), { wrapper })
    await act(() => retryHook.result.current.mutateAsync('t-1'))
    expect(retryTask).toHaveBeenCalledWith('t-1', expect.anything())
  })

  it('cleaned data 查询按数据源启用', async () => {
    const disabled = renderHook(() => useCleanedDataQuery(null, {}), { wrapper })
    expect(disabled.result.current.fetchStatus).toBe('idle')

    const { result } = renderHook(() => useCleanedDataQuery('ds-1', { page: 1 }), {
      wrapper,
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listCleanedData).toHaveBeenCalledWith('ds-1', { page: 1 })
  })

  it('cleaned detail 与 startCleaning', async () => {
    const detail = renderHook(() => useCleanedDataDetailQuery('ds-1', 'cd-1'), { wrapper })
    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true))
    expect(getCleanedData).toHaveBeenCalledWith('ds-1', 'cd-1')

    const startHook = renderHook(() => useStartCleaning(), { wrapper })
    await act(() =>
      startHook.result.current.mutateAsync({
        datasourceId: 'ds-1',
        config: { remove_duplicates: true, normalize_text: true },
      })
    )
    expect(startCleaning).toHaveBeenCalledWith('ds-1', {
      dataIds: undefined,
      config: { remove_duplicates: true, normalize_text: true },
    })
  })
})
