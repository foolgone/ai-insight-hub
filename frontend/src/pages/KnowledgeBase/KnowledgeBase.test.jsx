import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import KnowledgeBase from './index'
import { extractKnowledge, listFaq, listGaps, searchKnowledge } from '../../api/knowledge'
import { useDatasourceStore } from '../../stores/datasourceStore'

vi.mock('../../api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))

const FAQ = {
  id: 'f-1',
  question: '如何退款？',
  answer: '7 天内可无理由退款。',
  category: '售后',
  tags: ['退款'],
  confidence: 0.9,
  quality_score: 88,
  frequency: 10,
  source: 'extracted',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <KnowledgeBase />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('KnowledgeBasePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasourceStore.setState({ currentId: 'ds-1' })
    listFaq
      .mockResolvedValueOnce({
        items: [FAQ],
        pagination: { page: 1, has_next: true, total: 2 },
      })
      .mockResolvedValueOnce({
        items: [{ ...FAQ, id: 'f-2', question: '如何换货？' }],
        pagination: { page: 2, has_next: false, total: 2 },
      })
    listGaps.mockResolvedValue({
      gaps: [{ question: '支持分期吗？', frequency: 25, category: '支付', priority: 'high' }],
      summary: {},
    })
    searchKnowledge.mockResolvedValue({
      results: [{ ...FAQ, similarity: 0.92 }],
    })
    extractKnowledge.mockResolvedValue({ task_id: 't-1' })
  })

  afterEach(() => useDatasourceStore.setState({ currentId: null }))

  it('渲染 FAQ 列表并加载更多', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole('heading', { name: '知识库' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '如何退款？' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '加载更多' }))

    expect(await screen.findByRole('heading', { name: '如何换货？' })).toBeInTheDocument()
    expect(listFaq).toHaveBeenLastCalledWith('ds-1', { limit: 10, page: 2 })
  })

  it('盲区 Tab 展示并转为 FAQ', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '如何退款？' })

    await user.click(screen.getByRole('tab', { name: '知识盲区' }))

    expect(await screen.findByText('支持分期吗？')).toBeInTheDocument()
    expect(screen.getByText('高优先级')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '转为 FAQ' }))
    expect(await screen.findByRole('dialog', { name: '新建知识条目' })).toBeInTheDocument()
    expect(screen.getByLabelText(/问题/)).toHaveValue('支持分期吗？')
  })

  it('搜索 Tab 调用检索并展示相似度', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '如何退款？' })

    await user.click(screen.getByRole('tab', { name: '知识检索' }))
    await user.type(screen.getByLabelText('知识检索关键词'), '退款')
    await user.click(screen.getByRole('button', { name: '搜索' }))

    expect(await screen.findByText('相似度 92%')).toBeInTheDocument()
    expect(searchKnowledge).toHaveBeenCalledWith('ds-1', { q: '退款', limit: 10 })
  })

  it('打开提取知识弹窗并启动', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '如何退款？' })

    await user.click(screen.getByRole('button', { name: '提取知识' }))
    await user.click(await screen.findByRole('button', { name: '启动提取' }))

    await waitFor(() =>
      expect(extractKnowledge).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({ min_frequency: 3 })
      )
    )
  })

  it('新建条目打开 Drawer', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: '如何退款？' })

    await user.click(screen.getByRole('button', { name: '新建条目' }))

    expect(await screen.findByRole('dialog', { name: '新建知识条目' })).toBeInTheDocument()
  })

  it('未选择数据源时展示引导', async () => {
    useDatasourceStore.setState({ currentId: null })
    renderPage()

    expect(await screen.findByText('尚未选择数据源')).toBeInTheDocument()
    expect(listFaq).not.toHaveBeenCalled()
  })
})
