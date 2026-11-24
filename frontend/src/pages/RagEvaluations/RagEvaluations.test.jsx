import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RagEvaluations from './index'
import { listDatasets, listRagEvaluations } from '../../api/ragEvaluations'

vi.mock('../../api/ragEvaluations', () => ({
  listRagEvaluations: vi.fn(),
  listRagEvaluationResults: vi.fn(),
  listRagEvaluationFailures: vi.fn(),
  createRagEvaluation: vi.fn(),
  listDatasets: vi.fn(),
  listDatasetVersions: vi.fn(),
}))

const RUN = {
  id: 'run-1',
  dataset_name: '售后政策评测集',
  dataset_version_id: 'version-12345678',
  execution_mode: 'query',
  adapter: 'mock',
  total_items: 10,
  evaluated_items: 7,
  invalid_items: 2,
  failed_items: 1,
  skipped_items: 0,
  unprocessed_items: 0,
  completed_items: 10,
  status: 'completed',
  created_at: '2026-11-24T10:00:00Z',
  completed_at: '2026-11-24T10:02:00Z',
  aggregate: {
    metrics: {
      faithfulness: { mean: 0.75, evaluated: 7, invalid: 1, failed: 0, skipped: 0 },
      answer_correctness: { mean: 0.9, evaluated: 7, invalid: 0, failed: 0, skipped: 0 },
      answer_relevancy: { mean: null, evaluated: 0, invalid: 1, failed: 0, skipped: 0 },
    },
  },
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/rag-evaluations']}>
        <RagEvaluations />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RagEvaluationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRagEvaluations.mockResolvedValue({
      items: [RUN],
      pagination: { page: 1, limit: 10, total: 1, pages: 1 },
    })
    listDatasets.mockResolvedValue({ items: [], pagination: { total: 0 } })
  })

  afterEach(() => vi.clearAllMocks())

  it('展示 Beta 提示、Run 行、F/C/R 与 invalid 计数', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'RAG 评测' })).toBeInTheDocument()
    expect(screen.getByRole('note', { name: '评测 Beta 与已知限制' })).toBeInTheDocument()
    expect(await screen.findByText('售后政策评测集')).toBeInTheDocument()
    expect(screen.getByText('已完成')).toBeInTheDocument()
    expect(screen.getByText('invalid 2')).toBeInTheDocument()
    expect(screen.getByText('failed 1')).toBeInTheDocument()
    expect(screen.getByText('0.75')).toBeInTheDocument()
    expect(screen.getByText('0.90')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看详情' })).toHaveAttribute(
      'href',
      '/rag-evaluations/run-1'
    )
  })

  it('打开新建评测弹窗并提示无数据集', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: 'RAG 评测' })

    await user.click(screen.getByRole('button', { name: '新建评测' }))

    expect(await screen.findByRole('dialog', { name: '新建 RAG 评测' })).toBeInTheDocument()
    expect(await screen.findByText(/还没有 QA 数据集/)).toBeInTheDocument()
    expect(listDatasets).toHaveBeenCalled()
  })

  it('空列表展示 Empty', async () => {
    listRagEvaluations.mockResolvedValue({
      items: [],
      pagination: { page: 1, limit: 10, total: 0, pages: 0 },
    })
    renderPage()
    expect(await screen.findByText('还没有 RAG 评测 Run')).toBeInTheDocument()
  })
})
