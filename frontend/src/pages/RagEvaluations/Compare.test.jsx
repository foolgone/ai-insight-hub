import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RagEvaluationCompare from './Compare'
import {
  getRagEvaluation,
  listAllDatasetItems,
  listAllRagEvaluationResults,
  listDatasetItems,
  listRagEvaluationResults,
  listRagEvaluations,
} from '../../api/ragEvaluations'

vi.mock('../../api/ragEvaluations', () => ({
  listRagEvaluations: vi.fn(),
  getRagEvaluation: vi.fn(),
  listRagEvaluationResults: vi.fn(),
  listAllRagEvaluationResults: vi.fn(),
  listDatasetItems: vi.fn(),
  listAllDatasetItems: vi.fn(),
}))

const BASE_RUN = {
  id: 'run-a',
  dataset_id: 'ds-1',
  dataset_version_id: 'v-1',
  dataset_name: 'M2 P0 验收数据集',
  status: 'completed',
  execution_mode: 'query',
  adapter: 'mock',
  total_items: 4,
  completed_items: 4,
  evaluated_items: 3,
  invalid_items: 1,
  failed_items: 0,
  skipped_items: 0,
  unprocessed_items: 0,
  completed_at: '2026-11-24T10:00:00Z',
  aggregate: {
    metrics: {
      faithfulness: { mean: 0.5, evaluated: 3, invalid: 1, failed: 0, skipped: 0 },
      answer_correctness: { mean: 0.5, evaluated: 3, invalid: 0, failed: 0, skipped: 0 },
      answer_relevancy: { mean: 0.5, evaluated: 3, invalid: 0, failed: 0, skipped: 0 },
    },
  },
}

const TARGET_RUN = {
  ...BASE_RUN,
  id: 'run-b',
  dataset_version_id: 'v-1',
  evaluated_items: 4,
  invalid_items: 1,
  aggregate: {
    metrics: {
      faithfulness: { mean: 0.7, evaluated: 4, invalid: 1, failed: 0, skipped: 0 },
      answer_correctness: { mean: 0.6, evaluated: 4, invalid: 0, failed: 0, skipped: 0 },
      answer_relevancy: { mean: 0.5, evaluated: 4, invalid: 0, failed: 0, skipped: 0 },
    },
  },
}

const ITEMS = [
  { id: 'item-1', item_key: 'Q01', query: '退款多久审批？' },
  { id: 'item-2', item_key: 'Q02', query: '发票怎么开？' },
  { id: 'item-3', item_key: 'Q03', query: '运费谁承担？' },
  { id: 'item-4', item_key: 'Q04', query: '质量问题怎么办？' },
]

const BASE_RESULTS = [
  {
    id: 'b1',
    dataset_item_id: 'item-1',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.5,
  },
  {
    id: 'b2',
    dataset_item_id: 'item-2',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.8,
  },
  {
    id: 'b3',
    dataset_item_id: 'item-3',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.4,
  },
  {
    id: 'b4',
    dataset_item_id: 'item-4',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.6,
  },
]

const TARGET_RESULTS = [
  {
    id: 't1',
    dataset_item_id: 'item-1',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.8,
  },
  {
    id: 't2',
    dataset_item_id: 'item-2',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.5,
  },
  {
    id: 't3',
    dataset_item_id: 'item-3',
    metric_name: 'faithfulness',
    status: 'evaluated',
    score: 0.4,
  },
  { id: 't4', dataset_item_id: 'item-4', metric_name: 'faithfulness', status: 'invalid' },
]

function renderAt(path) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/rag-evaluations/compare" element={<RagEvaluationCompare />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('RagEvaluationCompare', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRagEvaluations.mockResolvedValue({ items: [BASE_RUN, TARGET_RUN] })
    getRagEvaluation.mockImplementation(async runId => (runId === 'run-a' ? BASE_RUN : TARGET_RUN))
    listRagEvaluationResults.mockImplementation(async runId => ({
      items: runId === 'run-a' ? BASE_RESULTS : TARGET_RESULTS,
    }))
    listAllRagEvaluationResults.mockImplementation(async runId => {
      const payload = await listRagEvaluationResults(runId, { page: 1, limit: 100 })
      const items = payload.items || []
      return {
        items,
        total: items.length,
        loaded: items.length,
        truncated: false,
        totalPages: 1,
      }
    })
    listDatasetItems.mockResolvedValue({ items: ITEMS })
    listAllDatasetItems.mockImplementation(async () => ({
      items: ITEMS,
      total: ITEMS.length,
      loaded: ITEMS.length,
      truncated: false,
      totalPages: 1,
    }))
  })

  it('加载完成后导出 CSV/JSON 按钮可用', async () => {
    renderAt('/rag-evaluations/compare?base=run-a&target=run-b')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '导出 CSV' })).toBeEnabled()
    })
    expect(screen.getByRole('button', { name: '导出 JSON' })).toBeEnabled()
  })

  it('展示指标 delta 与 Case 级 improved/regressed/unchanged/invalid', async () => {
    renderAt('/rag-evaluations/compare?base=run-a&target=run-b')

    expect(await screen.findByRole('heading', { name: 'Run 对比' })).toBeInTheDocument()
    expect(await screen.findByText('+0.200')).toBeInTheDocument()
    expect(await screen.findByText('Case 级变化')).toBeInTheDocument()
    expect(await screen.findByText(/±0.2/)).toBeInTheDocument()
    expect(await screen.findByText(/同配置比较/)).toBeInTheDocument()
    expect(await screen.findByText('+0.100')).toBeInTheDocument()
    expect(await screen.findByText('变好')).toBeInTheDocument()
    expect(await screen.findByText('变差')).toBeInTheDocument()
    expect(await screen.findByText('不变')).toBeInTheDocument()
    expect((await screen.findAllByText('invalid')).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: '查看 Case' })[0]).toHaveAttribute(
      'href',
      '/rag-evaluations/run-b/cases/item-1'
    )
  })

  it('250 个 Case 分页加载，仅对比前 200 并提示', async () => {
    const total = 250
    const makeRows = () =>
      Array.from({ length: total }, (_, index) => ({
        id: `row-${index}`,
        dataset_item_id: `item-${index}`,
        metric_name: 'faithfulness',
        status: 'evaluated',
        score: 0.5,
      }))
    listAllRagEvaluationResults.mockImplementation(async () => ({
      items: makeRows(),
      total,
      loaded: total,
      truncated: false,
      totalPages: 1,
    }))
    listDatasetItems.mockResolvedValue({ items: [] })

    renderAt('/rag-evaluations/compare?base=run-a&target=run-b')

    expect(await screen.findByText(/仅对比前 200 个 Case/)).toBeInTheDocument()
    expect(await screen.findByText(/Base 250\/250/)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '查看 Case' })).toHaveLength(200)
  })

  it('不同 adapter 时不显示同配置强警告', async () => {
    getRagEvaluation.mockImplementation(async runId =>
      runId === 'run-a' ? BASE_RUN : { ...TARGET_RUN, adapter: 'weknora' }
    )
    renderAt('/rag-evaluations/compare?base=run-a&target=run-b')
    await screen.findByText('Case 级变化')
    expect(screen.queryByText(/同配置比较/)).not.toBeInTheDocument()
    expect(screen.getByText(/±0.2/)).toBeInTheDocument()
  })

  it('版本不一致时给出明确警告', async () => {
    getRagEvaluation.mockImplementation(async runId =>
      runId === 'run-a' ? BASE_RUN : { ...TARGET_RUN, dataset_version_id: 'v-2' }
    )
    renderAt('/rag-evaluations/compare?base=run-a&target=run-b')
    expect(await screen.findByText(/版本不一致/)).toBeInTheDocument()
  })

  it('completed Run 不足两个时给出空态', async () => {
    listRagEvaluations.mockResolvedValue({ items: [BASE_RUN] })
    renderAt('/rag-evaluations/compare')
    expect(await screen.findByText('至少需要两个 completed Run')).toBeInTheDocument()
  })
})
