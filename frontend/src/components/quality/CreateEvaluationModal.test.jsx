import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CreateEvaluationModal } from './CreateEvaluationModal'
import { triggerQuality } from '../../api/quality'

vi.mock('../../api/quality', () => ({
  triggerQuality: vi.fn(),
  listQualityResults: vi.fn(),
  reviewQuality: vi.fn(),
}))

function renderModal(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateEvaluationModal open onClose={() => {}} datasourceId="ds-1" {...props} />
    </QueryClientProvider>
  )
}

describe('CreateEvaluationModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    triggerQuality.mockResolvedValue({ task_id: 't-1' })
  })

  it('默认 5 维全选并提交 config.dimensions/threshold', async () => {
    const user = userEvent.setup()
    renderModal()

    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes).toHaveLength(5)
    checkboxes.forEach(checkbox => expect(checkbox).toHaveAttribute('data-state', 'checked'))

    await user.click(screen.getByRole('button', { name: '启动评估' }))

    await waitFor(() =>
      expect(triggerQuality).toHaveBeenCalledWith('ds-1', {
        dataIds: undefined,
        dimensions: ['accuracy', 'completeness', 'hallucination', 'tone', 'compliance'],
        threshold: 70,
      })
    )
  })

  it('取消一个维度后提交 4 维', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('checkbox', { name: '语气' }))
    await user.click(screen.getByRole('button', { name: '启动评估' }))

    await waitFor(() =>
      expect(triggerQuality).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({
          dimensions: ['accuracy', 'completeness', 'hallucination', 'compliance'],
        })
      )
    )
  })

  it('全部取消时阻止提交', async () => {
    const user = userEvent.setup()
    renderModal()

    for (const label of ['准确性', '完整性', '幻觉控制', '语气', '合规性']) {
      await user.click(screen.getByRole('checkbox', { name: label }))
    }
    await user.click(screen.getByRole('button', { name: '启动评估' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('至少选择一个评估维度')
    expect(triggerQuality).not.toHaveBeenCalled()
  })

  it('无数据源时提示', async () => {
    const user = userEvent.setup()
    renderModal({ datasourceId: null })

    await user.click(screen.getByRole('button', { name: '启动评估' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('请先选择数据源')
    expect(triggerQuality).not.toHaveBeenCalled()
  })
})
