import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useCreateFaq,
  useDeleteFaq,
  useExtractKnowledge,
  useFaqInfiniteQuery,
  useGapsQuery,
  useKnowledgeSearchQuery,
  useUpdateFaq,
} from './useKnowledge'
import {
  createFaq,
  deleteFaq,
  extractKnowledge,
  listFaq,
  listGaps,
  searchKnowledge,
  updateFaq,
} from '../api/knowledge'

vi.mock('../api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))

function wrapper({ children }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useKnowledge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listFaq.mockResolvedValue({
      items: [{ id: 'f1' }],
      pagination: { page: 1, has_next: false, total: 1 },
    })
    searchKnowledge.mockResolvedValue({ results: [{ id: 'f1', similarity: 0.9 }] })
    listGaps.mockResolvedValue({ gaps: [{ question: 'q' }], summary: {} })
    extractKnowledge.mockResolvedValue({ task_id: 't-1' })
    createFaq.mockResolvedValue({ id: 'f2' })
    updateFaq.mockResolvedValue({ id: 'f1' })
    deleteFaq.mockResolvedValue({})
  })

  it('FAQ 无限列表与搜索/盲区查询', async () => {
    const faq = renderHook(() => useFaqInfiniteQuery('ds-1', { limit: 10 }), { wrapper })
    await waitFor(() => expect(faq.result.current.isSuccess).toBe(true))
    expect(listFaq).toHaveBeenCalledWith('ds-1', { limit: 10, page: 1 })

    const search = renderHook(() => useKnowledgeSearchQuery('ds-1', '退款', { limit: 10 }), {
      wrapper,
    })
    await waitFor(() => expect(search.result.current.isSuccess).toBe(true))
    expect(searchKnowledge).toHaveBeenCalledWith('ds-1', { q: '退款', limit: 10 })

    const gaps = renderHook(() => useGapsQuery('ds-1'), { wrapper })
    await waitFor(() => expect(gaps.result.current.isSuccess).toBe(true))
    expect(listGaps).toHaveBeenCalledWith('ds-1')
  })

  it('无数据源时 FAQ/搜索不请求', () => {
    renderHook(() => useFaqInfiniteQuery(null, {}), { wrapper })
    renderHook(() => useKnowledgeSearchQuery(null, '退款'), { wrapper })
    renderHook(() => useGapsQuery(null), { wrapper })

    expect(listFaq).not.toHaveBeenCalled()
    expect(searchKnowledge).not.toHaveBeenCalled()
    expect(listGaps).not.toHaveBeenCalled()
  })

  it('提取/创建/更新/删除 mutation', async () => {
    const extract = renderHook(() => useExtractKnowledge(), { wrapper })
    await act(() =>
      extract.result.current.mutateAsync({ datasourceId: 'ds-1', payload: { min_frequency: 3 } })
    )
    expect(extractKnowledge).toHaveBeenCalledWith('ds-1', { min_frequency: 3 })

    const create = renderHook(() => useCreateFaq(), { wrapper })
    await act(() =>
      create.result.current.mutateAsync({ datasourceId: 'ds-1', payload: { question: 'q' } })
    )
    expect(createFaq).toHaveBeenCalledWith('ds-1', { question: 'q' })

    const update = renderHook(() => useUpdateFaq(), { wrapper })
    await act(() =>
      update.result.current.mutateAsync({
        datasourceId: 'ds-1',
        faqId: 'f1',
        payload: { answer: 'a' },
      })
    )
    expect(updateFaq).toHaveBeenCalledWith('ds-1', 'f1', { answer: 'a' })

    const remove = renderHook(() => useDeleteFaq(), { wrapper })
    await act(() => remove.result.current.mutateAsync({ datasourceId: 'ds-1', faqId: 'f1' }))
    expect(deleteFaq).toHaveBeenCalledWith('ds-1', 'f1')
  })
})
