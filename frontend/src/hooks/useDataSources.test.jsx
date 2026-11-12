import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useCreateDataSource,
  useDataSourceQuery,
  useDataSourcesQuery,
  useDeleteDataSource,
  useUpdateDataSource,
  useUploadDataSourceFile,
  useRawDataQuery,
  useStructureRawData,
} from './useDataSources'
import {
  createDataSource,
  deleteDataSource,
  getDataSource,
  listDataSources,
  updateDataSource,
  uploadDataSourceFile,
  listRawData,
  structureRawData,
} from '../api/datasources'

vi.mock('../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
  listRawData: vi.fn(),
  structureRawData: vi.fn(),
}))

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useDataSources', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listDataSources.mockResolvedValue({ items: [], pagination: { total: 0 } })
    getDataSource.mockResolvedValue({ id: 'ds-1' })
    createDataSource.mockResolvedValue({ id: 'ds-1' })
    updateDataSource.mockResolvedValue({ id: 'ds-1' })
    deleteDataSource.mockResolvedValue({ deleted_records: 1 })
    uploadDataSourceFile.mockResolvedValue({ task_id: 't-1' })
  })

  it('useDataSourcesQuery 调用列表接口', async () => {
    const { result } = renderHook(() => useDataSourcesQuery({ page: 1 }), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listDataSources).toHaveBeenCalledWith({ page: 1 })
  })

  it('useDataSourceQuery 无 id 时不请求', () => {
    renderHook(() => useDataSourceQuery(null), { wrapper })

    expect(getDataSource).not.toHaveBeenCalled()
  })

  it('useDataSourceQuery 有 id 时请求详情', async () => {
    const { result } = renderHook(() => useDataSourceQuery('ds-1'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(getDataSource).toHaveBeenCalledWith('ds-1')
  })

  it('创建/更新/删除/上传 mutation 调用对应 API', async () => {
    const createHook = renderHook(() => useCreateDataSource(), { wrapper })
    await act(() => createHook.result.current.mutateAsync({ name: 'a', type: 'other' }))
    expect(createDataSource).toHaveBeenCalledWith({ name: 'a', type: 'other' }, expect.anything())

    const updateHook = renderHook(() => useUpdateDataSource(), { wrapper })
    await act(() => updateHook.result.current.mutateAsync({ id: 'ds-1', payload: { name: 'b' } }))
    expect(updateDataSource).toHaveBeenCalledWith('ds-1', { name: 'b' })

    const deleteHook = renderHook(() => useDeleteDataSource(), { wrapper })
    await act(() => deleteHook.result.current.mutateAsync({ id: 'ds-1', force: true }))
    expect(deleteDataSource).toHaveBeenCalledWith('ds-1', { force: true })

    const uploadHook = renderHook(() => useUploadDataSourceFile(), { wrapper })
    const file = new File(['x'], 'a.csv')
    await act(() => uploadHook.result.current.mutateAsync({ id: 'ds-1', file }))
    expect(uploadDataSourceFile).toHaveBeenCalledWith('ds-1', file)
  })

  it('上传可携带进度回调（#4）', async () => {
    const uploadHook = renderHook(() => useUploadDataSourceFile(), { wrapper })
    const file = new File(['x'], 'a.csv')
    const onProgress = vi.fn()

    await act(() => uploadHook.result.current.mutateAsync({ id: 'ds-1', file, onProgress }))

    expect(uploadDataSourceFile).toHaveBeenCalledWith('ds-1', file, onProgress)
  })

  it('转写文件列表与会重新切分（#1）', async () => {
    listRawData.mockResolvedValue({ items: [{ id: 'raw-1' }] })
    structureRawData.mockResolvedValue({ task_id: 't-9' })

    const rawHook = renderHook(() => useRawDataQuery('ds-1'), { wrapper })
    await waitFor(() => expect(rawHook.result.current.isSuccess).toBe(true))
    expect(listRawData).toHaveBeenCalledWith('ds-1')

    const structureHook = renderHook(() => useStructureRawData(), { wrapper })
    await act(() =>
      structureHook.result.current.mutateAsync({ datasourceId: 'ds-1', rawId: 'raw-1' })
    )
    expect(structureRawData).toHaveBeenCalledWith('ds-1', 'raw-1')
  })
})
