import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QualityAssessmentDetail from './Detail'
import { ReviewModal } from '../../components/quality/ReviewModal'
import { listQualityResults, reviewQuality } from '../../api/quality'
import { getCleanedData } from '../../api/cleaning'
import { useDatasourceStore } from '../../stores/datasourceStore'

vi.mock('../../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))
vi.mock('../../api/cleaning', () => ({
  startCleaning: vi.fn(),
  listCleanedData: vi.fn(),
  getCleanedData: vi.fn(),
}))

const RESULT = {
  id: 'q-1',
  data_id: 'cd-1',
  overall_score: 82,
  needs_review: true,
  quality_level: 'good',
  agent_version: 'v1.0.0',
  created_at: '2026-10-24T10:00:00Z',
  dimensions: {
    accuracy: { score: 90, issues: [] },
    completeness: { score: 70, issues: ['缺少配置信息'] },
    hallucination: { score: 80, issues: [] },
    tone: { score: 85, issues: [] },
    compliance: { score: 95, issues: [] },
  },
}

function renderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/quality-assessment/q-1']}>
        <Routes>
          <Route path="/quality-assessment/:id" element={<QualityAssessmentDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('QualityAssessmentDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasourceStore.setState({ currentId: 'ds-1' })
    listQualityResults.mockResolvedValue({
      items: [RESULT],
      pagination: { total: 1 },
    })
    getCleanedData.mockResolvedValue({
      user_message: '如何退款？',
      ai_response: '7 天内可退款。',
    })
    reviewQuality.mockResolvedValue({ id: 'q-1', decision: 'approved' })
  })

  afterEach(() => useDatasourceStore.setState({ currentId: null }))

  it('展示总分、5 维得分、维度问题与对话原文', async () => {
    renderDetail()

    expect(await screen.findByRole('heading', { name: '评估详情' })).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: '质量分 82' })).toBeInTheDocument()
    expect(await screen.findByRole('region', { name: '5 维得分' })).toBeInTheDocument()
    expect(screen.getByText('缺少配置信息')).toBeInTheDocument()
    expect(await screen.findByText('如何退款？')).toBeInTheDocument()
    expect(screen.getByText('7 天内可退款。')).toBeInTheDocument()
    expect(screen.getByText('待人工复核')).toBeInTheDocument()
  })

  it('点击人工复核打开复核弹窗', async () => {
    const user = userEvent.setup()
    renderDetail()
    await screen.findByRole('heading', { name: '评估详情' })

    await user.click(await screen.findByRole('button', { name: '人工复核' }))

    expect(await screen.findByRole('dialog', { name: '人工复核' })).toBeInTheDocument()
  })

  it('找不到结果时展示空态', async () => {
    listQualityResults.mockResolvedValue({ items: [], pagination: { total: 0 } })
    renderDetail()

    expect(await screen.findByText('未找到评估结果')).toBeInTheDocument()
  })
})

describe('ReviewModal', () => {
  function renderReview() {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    return render(
      <QueryClientProvider client={queryClient}>
        <ReviewModal open onClose={() => {}} datasourceId="ds-1" result={RESULT} />
      </QueryClientProvider>
    )
  }

  beforeEach(() => {
    vi.clearAllMocks()
    reviewQuality.mockResolvedValue({ id: 'q-1', decision: 'approved' })
  })

  it('默认通过并提交', async () => {
    const user = userEvent.setup()
    renderReview()

    await user.click(screen.getByRole('button', { name: '提交复核' }))

    await waitFor(() =>
      expect(reviewQuality).toHaveBeenCalledWith('ds-1', 'q-1', { decision: 'approved' })
    )
  })

  it('修正分数时提交 corrected_scores', async () => {
    const user = userEvent.setup()
    renderReview()

    await user.click(screen.getByRole('radio', { name: '修正分数' }))
    await user.clear(await screen.findByLabelText('准确性'))
    await user.type(screen.getByLabelText('准确性'), '95')
    await user.click(screen.getByRole('button', { name: '提交复核' }))

    await waitFor(() =>
      expect(reviewQuality).toHaveBeenCalledWith(
        'ds-1',
        'q-1',
        expect.objectContaining({
          decision: 'corrected',
          corrected_scores: expect.objectContaining({ accuracy: 95 }),
        })
      )
    )
  })
})
