import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RagEvaluationDetail from './Detail'
import {
  getRagEvaluation,
  listDatasetItems,
  listRagEvaluationFailures,
  listRagEvaluationResults,
} from '../../api/ragEvaluations'

vi.mock('../../api/ragEvaluations', () => ({
  getRagEvaluation: vi.fn(),
  listRagEvaluationResults: vi.fn(),
  listRagEvaluationFailures: vi.fn(),
  listDatasetItems: vi.fn(),
}))

const RUN = {
  id: 'run-1',
  dataset_id: 'ds-1',
  dataset_name: '售后政策评测集',
  dataset_version_id: 'version-1',
  execution_mode: 'query',
  adapter: 'mock',
  total_items: 2,
  evaluated_items: 1,
  invalid_items: 1,
  failed_items: 0,
  skipped_items: 0,
  unprocessed_items: 0,
  completed_items: 2,
  status: 'completed',
  error_message: null,
  created_at: '2026-11-24T10:00:00Z',
  completed_at: '2026-11-24T10:02:00Z',
  aggregate: {
    metrics: {
      faithfulness: { mean: 0.75, evaluated: 1, invalid: 1, failed: 0, skipped: 0, coverage: 0.5 },
      answer_correctness: {
        mean: 0.9,
        evaluated: 1,
        invalid: 0,
        failed: 0,
        skipped: 0,
        coverage: 0.5,
      },
      answer_relevancy: {
        mean: 0.8,
        evaluated: 1,
        invalid: 0,
        failed: 0,
        skipped: 0,
        coverage: 0.5,
      },
    },
  },
}

const RESULTS = [
  {
    id: 'r1',
    dataset_item_id: 'item-1',
    trace_id: 'trace-1',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 1,
    details: {},
  },
  {
    id: 'r2',
    dataset_item_id: 'item-1',
    trace_id: 'trace-1',
    metric_name: 'answer_correctness',
    status: 'evaluated',
    score: 0.9,
    details: {},
  },
  {
    id: 'r3',
    dataset_item_id: 'item-2',
    trace_id: 'trace-2',
    metric_name: 'faithfulness',
    status: 'invalid',
    invalid_reason: 'contract_violation',
    details: {},
  },
]

const FAILURES = [
  {
    id: 'r3',
    dataset_item_id: 'item-2',
    metric_name: 'faithfulness',
    status: 'invalid',
    invalid_reason: 'contract_violation',
  },
]

const ITEMS = [
  { id: 'item-1', item_key: 'Q01', query: '第 10 天还能无理由退款吗？' },
  { id: 'item-2', item_key: 'Q02', query: '运费谁承担？' },
]

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/rag-evaluations/run-1']}>
        <Routes>
          <Route path="/rag-evaluations/:runId" element={<RagEvaluationDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RagEvaluationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRagEvaluation.mockResolvedValue(RUN)
    listRagEvaluationResults.mockResolvedValue({ items: RESULTS })
    listRagEvaluationFailures.mockResolvedValue({ items: FAILURES })
    listDatasetItems.mockResolvedValue({ items: ITEMS })
  })

  it('展示指标、样本进度、known issues、case 与报告入口', async () => {
    renderPage()

    expect(await screen.findByText('评测 Run 详情')).toBeInTheDocument()
    expect(screen.getByText(/售后政策评测集/)).toBeInTheDocument()
    expect(screen.getByRole('note', { name: '评测 Beta 与已知限制' })).toBeInTheDocument()
    expect(screen.getByText('Known issues')).toBeInTheDocument()
    expect(screen.getByText('invalid 结果')).toBeInTheDocument()
    expect(screen.getByText('0.750')).toBeInTheDocument()
    expect(screen.getByText('0.900')).toBeInTheDocument()
    expect(await screen.findByText('Q01')).toBeInTheDocument()
    expect(await screen.findByText('Q02')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '去报告中心' })).toHaveAttribute('href', '/reports')
    expect(screen.getAllByRole('link', { name: '查看 Case' })[0]).toHaveAttribute(
      'href',
      '/rag-evaluations/run-1/cases/item-1'
    )
    expect(screen.getAllByText(/输出契约不合法/).length).toBeGreaterThan(0)
  })

  it('Run 不存在时给出返回入口', async () => {
    getRagEvaluation.mockResolvedValue(null)
    renderPage()
    expect(await screen.findByText('未找到评测 Run')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回 Run 列表' })).toHaveAttribute(
      'href',
      '/rag-evaluations'
    )
  })
})
