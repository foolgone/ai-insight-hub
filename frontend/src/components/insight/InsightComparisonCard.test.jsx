import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InsightComparisonCard } from './InsightComparisonCard'
import { compareInsightRuns, listQualityRuns } from '../../api/quality'

vi.mock('../../api/quality', () => ({
  listQualityRuns: vi.fn(),
  compareInsightRuns: vi.fn(),
  compareQualityRuns: vi.fn(),
  listQualityResults: vi.fn(),
  triggerQuality: vi.fn(),
  reviewQuality: vi.fn(),
}))

const RUN_A = {
  task_id: 'run-a',
  task_type: 'analyze',
  status: 'completed',
  created_at: '2026-11-01T10:00:00Z',
  completed_at: '2026-11-01T10:05:00Z',
  sample_count: 0,
}
const RUN_B = { ...RUN_A, task_id: 'run-b', completed_at: '2026-11-08T10:05:00Z' }

const COMPARISON = {
  base_task_id: 'run-a',
  target_task_id: 'run-b',
  sentiment: [
    { name: '正面', base: 0.3, target: 0.5, delta: 0.2 },
    { name: '负面', base: 0.2, target: 0.1, delta: -0.1 },
  ],
  intents: [{ name: '退款', base: 10, target: 6, delta: -4 }],
  pain_points_added: ['发票开具流程复杂'],
  pain_points_removed: ['物流更新不及时'],
}

function renderCard(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <InsightComparisonCard datasourceId="ds-1" {...props} />
    </QueryClientProvider>
  )
}

describe('InsightComparisonCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listQualityRuns.mockResolvedValue({ items: [RUN_B, RUN_A] })
    compareInsightRuns.mockResolvedValue(COMPARISON)
  })

  it('自动对比最近两次洞察分析', async () => {
    renderCard()

    expect(await screen.findByText('30% → 50%')).toBeInTheDocument()
    expect(screen.getByText('+0.2')).toBeInTheDocument()
    expect(compareInsightRuns).toHaveBeenCalledWith('ds-1', 'run-a', 'run-b')
  })

  it('展示意图变化与痛点增减', async () => {
    renderCard()

    expect(await screen.findByText('退款')).toBeInTheDocument()
    expect(screen.getByText('10 → 6')).toBeInTheDocument()
    expect(screen.getByText('-4 次')).toBeInTheDocument()
    expect(screen.getByText('发票开具流程复杂')).toBeInTheDocument()
    expect(screen.getByText('物流更新不及时')).toBeInTheDocument()
  })

  it('不足两次洞察分析时不渲染', async () => {
    listQualityRuns.mockResolvedValue({ items: [RUN_B] })

    renderCard()

    // 等待请求完成后卡片消失
    await screen.findByText('尚未选择数据源').catch(() => {})
    expect(screen.queryByText('洞察对比')).toBeNull()
  })

  it('无数据源时不请求', () => {
    renderCard({ datasourceId: null })

    expect(listQualityRuns).not.toHaveBeenCalled()
  })
})
