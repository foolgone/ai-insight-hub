import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RunComparisonPanel } from './RunComparisonPanel'
import { compareQualityRuns, listQualityRuns } from '../../api/quality'

vi.mock('../../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
  listQualityRuns: vi.fn(),
  compareQualityRuns: vi.fn(),
}))

const TARGET_RUN = {
  task_id: 'run-b',
  task_type: 'evaluate',
  status: 'completed',
  created_at: '2026-11-08T10:00:00Z',
  completed_at: '2026-11-08T10:05:00Z',
  sample_count: 2,
  avg_overall_score: 70,
  evaluated: 2,
  needs_review: 0,
}

const BASE_RUN = {
  task_id: 'run-a',
  task_type: 'evaluate',
  status: 'completed',
  created_at: '2026-11-01T10:00:00Z',
  completed_at: '2026-11-01T10:05:00Z',
  sample_count: 2,
  avg_overall_score: 65,
  evaluated: 2,
  needs_review: 1,
}

const COMPARISON = {
  base: {
    task_id: 'run-a',
    status: 'completed',
    completed_at: '2026-11-01T10:05:00Z',
    sample_count: 2,
    avg_overall_score: 65,
    needs_review: 1,
    dimension_averages: { accuracy: 58 },
    bands: { excellent: 0, good: 0, fair: 1, poor: 1 },
  },
  target: {
    task_id: 'run-b',
    status: 'completed',
    completed_at: '2026-11-08T10:05:00Z',
    sample_count: 2,
    avg_overall_score: 70,
    needs_review: 0,
    dimension_averages: { accuracy: 63 },
    bands: { excellent: 0, good: 1, fair: 1, poor: 0 },
  },
  delta: {
    avg_overall_score: 5,
    sample_count: 0,
    needs_review: -1,
    dimension_averages: { accuracy: 5 },
    bands: { excellent: 0, good: 1, fair: 0, poor: -1 },
  },
  dimensions: [{ name: 'accuracy', base: 58, target: 63, delta: 5 }],
  regressions: [
    {
      data_id: '11111111-1111-1111-1111-111111111111',
      base_score: 70,
      target_score: 65,
      delta: -5,
    },
  ],
  improvements: [
    {
      data_id: '22222222-2222-2222-2222-222222222222',
      base_score: 60,
      target_score: 75,
      delta: 15,
    },
  ],
  added_items: 0,
  removed_items: 0,
  issues_added: ['回答超出知识库范围（1 条）'],
  issues_removed: ['未回答运费问题（1 条）'],
  categories: [
    { category: 'missing_knowledge', label: '知识缺失', base: 2, target: 1, delta: -1 },
    { category: 'hallucination', label: '幻觉/编造', base: 1, target: 0, delta: -1 },
  ],
}

function renderPanel(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <RunComparisonPanel datasourceId="ds-1" {...props} />
    </QueryClientProvider>
  )
}

describe('RunComparisonPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listQualityRuns.mockResolvedValue({ items: [TARGET_RUN, BASE_RUN] })
    compareQualityRuns.mockResolvedValue(COMPARISON)
  })

  it('批次不足两个时给出引导', async () => {
    listQualityRuns.mockResolvedValue({ items: [TARGET_RUN] })

    renderPanel()

    expect(await screen.findByText('暂无可对比的批次')).toBeInTheDocument()
    expect(compareQualityRuns).not.toHaveBeenCalled()
  })

  it('默认用最新批次对比上一批次', async () => {
    renderPanel()

    expect(await screen.findByText('65.0 → 70.0')).toBeInTheDocument()
    expect(compareQualityRuns).toHaveBeenCalledWith('ds-1', 'run-a', 'run-b')
  })

  it('展示平均分、待复核与档位变化', async () => {
    renderPanel()

    // +5.0 分同时出现在「平均总分」和维度变化里，用 findAll
    expect((await screen.findAllByText('+5.0 分')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('-1.0 条').length).toBeGreaterThan(0)
    expect(screen.getByText('1 → 0')).toBeInTheDocument()
  })

  it('展示维度变化、退步/进步对话与问题差集', async () => {
    renderPanel()

    expect(await screen.findByText('准确性')).toBeInTheDocument()
    expect(screen.getByText('58.0')).toBeInTheDocument()
    expect(screen.getByText('63.0')).toBeInTheDocument()

    expect(screen.getByText('22222222')).toBeInTheDocument()
    expect(screen.getByText('60.0 → 75.0')).toBeInTheDocument()
    expect(screen.getByText('70.0 → 65.0')).toBeInTheDocument()

    expect(screen.getByText('回答超出知识库范围（1 条）')).toBeInTheDocument()
    expect(screen.getByText('未回答运费问题（1 条）')).toBeInTheDocument()
  })

  it('展示问题分类变化（知识缺失/幻觉）', async () => {
    renderPanel()

    expect(await screen.findByText('知识缺失')).toBeInTheDocument()
    expect(screen.getByText('幻觉/编造')).toBeInTheDocument()
    // 分类差值（与「待复核」的 -1 条同文案，用 findAll）
    expect(screen.getAllByText('-1.0 条').length).toBeGreaterThanOrEqual(2)
  })

  it('基线与对比选同一批次时给出提示且不请求', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText('65.0 → 70.0')
    compareQualityRuns.mockClear()

    await user.click(screen.getByRole('combobox', { name: '基线批次' }))
    const options = await screen.findAllByRole('option')
    // 选中「对比」批次（最新的一批）作为基线 → 两边相同
    await user.click(options[0])

    expect(await screen.findByText('基线与对比不能是同一个批次，请重新选择。')).toBeInTheDocument()
    expect(compareQualityRuns).not.toHaveBeenCalled()
  })

  it('对比接口失败时展示错误而不是空白', async () => {
    compareQualityRuns.mockRejectedValue(new Error('Run has no results linked to it'))

    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('Run has no results')
  })

  it('没有数据源时不渲染', () => {
    renderPanel({ datasourceId: null })

    expect(screen.queryByText('批次对比')).not.toBeInTheDocument()
    expect(listQualityRuns).not.toHaveBeenCalled()
  })
})
