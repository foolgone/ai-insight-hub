import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FaqDrawer } from './FaqDrawer'
import { ExtractKnowledgeModal } from './ExtractKnowledgeModal'
import { createFaq, extractKnowledge, updateFaq } from '../../api/knowledge'

vi.mock('../../api/knowledge', () => ({
  listFaq: vi.fn(),
  searchKnowledge: vi.fn(),
  listGaps: vi.fn(),
  extractKnowledge: vi.fn(),
  createFaq: vi.fn(),
  updateFaq: vi.fn(),
  deleteFaq: vi.fn(),
}))

function wrap(ui) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('FaqDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createFaq.mockResolvedValue({ id: 'f-1' })
    updateFaq.mockResolvedValue({ id: 'f-1' })
  })

  it('新建：预填问题、Markdown 预览并提交', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    wrap(<FaqDrawer open onClose={onClose} datasourceId="ds-1" prefillQuestion="如何退款？" />)

    expect(screen.getByLabelText(/问题/)).toHaveValue('如何退款？')
    await user.type(screen.getByLabelText(/答案/), '**7 天内**可退款')
    expect(screen.getByText('7 天内')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() =>
      expect(createFaq).toHaveBeenCalledWith('ds-1', {
        question: '如何退款？',
        answer: '**7 天内**可退款',
        tags: [],
      })
    )
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('答案为空时阻止提交', async () => {
    const user = userEvent.setup()
    wrap(<FaqDrawer open onClose={() => {}} datasourceId="ds-1" prefillQuestion="问题" />)

    await user.click(screen.getByRole('button', { name: '保存' }))

    expect(screen.getByRole('alert')).toHaveTextContent('请输入答案')
    expect(createFaq).not.toHaveBeenCalled()
  })

  it('编辑模式回显并提交 PATCH', async () => {
    const user = userEvent.setup()
    wrap(
      <FaqDrawer
        open
        onClose={() => {}}
        datasourceId="ds-1"
        faq={{
          id: 'f-1',
          question: '旧问题',
          answer: '旧答案',
          category: '售后',
          tags: ['退款'],
        }}
      />
    )

    expect(screen.getByLabelText(/问题/)).toHaveValue('旧问题')
    await user.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() =>
      expect(updateFaq).toHaveBeenCalledWith(
        'ds-1',
        'f-1',
        expect.objectContaining({ question: '旧问题', category: '售后', tags: ['退款'] })
      )
    )
  })
})

describe('ExtractKnowledgeModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    extractKnowledge.mockResolvedValue({ task_id: 't-1' })
  })

  it('提交默认提取参数', async () => {
    const user = userEvent.setup()
    wrap(<ExtractKnowledgeModal open onClose={() => {}} datasourceId="ds-1" />)

    await user.click(screen.getByRole('button', { name: '启动提取' }))

    await waitFor(() =>
      expect(extractKnowledge).toHaveBeenCalledWith('ds-1', {
        min_frequency: 3,
        similarity_threshold: 0.85,
        max_faq_count: 100,
      })
    )
  })

  it('无数据源时提示', async () => {
    const user = userEvent.setup()
    wrap(<ExtractKnowledgeModal open onClose={() => {}} datasourceId={null} />)

    await user.click(screen.getByRole('button', { name: '启动提取' }))

    expect(screen.getByRole('alert')).toHaveTextContent('请先选择数据源')
    expect(extractKnowledge).not.toHaveBeenCalled()
  })
})
