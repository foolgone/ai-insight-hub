import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RagEvaluationCaseDetail from './CaseDetail'
import {
  getDatasetItem,
  getRagEvaluation,
  getRagTrace,
  listRagEvaluationResults,
} from '../../api/ragEvaluations'

vi.mock('../../api/ragEvaluations', () => ({
  getRagEvaluation: vi.fn(),
  listRagEvaluationResults: vi.fn(),
  getDatasetItem: vi.fn(),
  getRagTrace: vi.fn(),
}))

const RUN = {
  id: 'run-1',
  dataset_id: 'ds-1',
  dataset_version_id: 'v-1',
  dataset_name: '售后政策评测集',
  execution_mode: 'query',
  adapter: 'mock',
  status: 'completed',
}

const ITEM = {
  id: 'item-1',
  item_key: 'Q01',
  query: '第 10 天还能无理由退款吗？',
  gold_answer: '不可以。',
  category: 'constraint',
}

const RESULTS = [
  {
    id: 'r1',
    dataset_item_id: 'item-1',
    trace_id: 'trace-1',
    metric_name: 'faithfulness',
    metric_version: 'v3',
    status: 'evaluated',
    invalid_reason: null,
    score: 0.75,
    latency_ms: 1200,
    raw_output: '{"claims":[]}',
    raw_truncated: false,
    details: {
      claims: [
        {
          claim_id: 'cl1',
          claim: '第 10 天已超过 7 天，不能无理由退款',
          claim_type: 'factual_claim',
          claim_subtype: 'derived',
          support_status: 'supported',
          is_contradictory: false,
          evidence_refs: [{ quote: '订单签收后 7 天内可申请无理由退款。' }],
        },
        {
          claim_id: 'cl2',
          claim: '质量问题不受 7 天限制',
          claim_type: 'factual_claim',
          claim_subtype: 'condition',
          support_status: 'insufficient_evidence',
          evidence_refs: [],
        },
      ],
    },
  },
  {
    id: 'r2',
    dataset_item_id: 'item-1',
    trace_id: 'trace-1',
    metric_name: 'answer_correctness',
    metric_version: 'v3',
    status: 'invalid',
    invalid_reason: 'contract_violation',
    score: null,
    latency_ms: 900,
    raw_output: null,
    raw_truncated: false,
    details: {},
  },
]

const TRACE = {
  trace_id: 'trace-1',
  query: '第 10 天还能无理由退款吗？',
  answer: '不可以。签收后 7 天内才可申请无理由退款。',
  retrieved_contexts: [
    {
      chunk_id: 'chunk-1',
      title: '退款时效',
      rank: 1,
      score: 0.92,
      content: '订单签收后 7 天内可申请无理由退款。',
    },
  ],
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/rag-evaluations/run-1/cases/item-1']}>
        <Routes>
          <Route
            path="/rag-evaluations/:runId/cases/:itemId"
            element={<RagEvaluationCaseDetail />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RagEvaluationCaseDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getRagEvaluation.mockResolvedValue(RUN)
    listRagEvaluationResults.mockResolvedValue({ items: RESULTS })
    getDatasetItem.mockResolvedValue(ITEM)
    getRagTrace.mockResolvedValue(TRACE)
  })

  it('展示 question/answer/contexts、claims/evidence 与 invalid 原因', async () => {
    renderPage()

    expect(await screen.findByText('Case 详情')).toBeInTheDocument()
    expect((await screen.findAllByText('第 10 天还能无理由退款吗？')).length).toBeGreaterThan(0)
    expect(await screen.findByText('不可以。签收后 7 天内才可申请无理由退款。')).toBeInTheDocument()
    expect((await screen.findAllByText('订单签收后 7 天内可申请无理由退款。')).length).toBeGreaterThan(0)
    expect(await screen.findByText('第 10 天已超过 7 天，不能无理由退款')).toBeInTheDocument()
    expect(await screen.findByText('“订单签收后 7 天内可申请无理由退款。”')).toBeInTheDocument()
    expect((await screen.findAllByText('insufficient')).length).toBeGreaterThan(0)
    expect(screen.queryByText('contradictory')).not.toBeInTheDocument()
    expect((await screen.findAllByText(/输出契约不合法/)).length).toBeGreaterThan(0)
    expect(await screen.findByText(/展开原始输出/)).toBeInTheDocument()
  })

  it('没有结果时给出提示', async () => {
    listRagEvaluationResults.mockResolvedValue({ items: [] })
    renderPage()
    expect(await screen.findByText('该 Case 在本 Run 中没有指标结果。')).toBeInTheDocument()
  })
})
