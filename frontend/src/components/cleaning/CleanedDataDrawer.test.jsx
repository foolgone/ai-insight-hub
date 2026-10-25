import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CleanedDataDrawer } from './CleanedDataDrawer'

const ITEM = {
  dialogue_id: 'dlg-1',
  timestamp: '2026-10-24T10:30:00Z',
  user_message: '如何退款？',
  ai_response: '7 天内可无理由退款。',
  quality_score: 92.5,
  issues: ['缺少退款时效'],
  metadata: { source: 'csv', session_id: 's-1' },
}

describe('CleanedDataDrawer', () => {
  it('展示对话、质量分、问题与元数据', () => {
    render(<CleanedDataDrawer item={ITEM} open onClose={() => {}} />)

    expect(screen.getByRole('dialog', { name: '清洗结果详情' })).toBeInTheDocument()
    expect(screen.getByText('如何退款？')).toBeInTheDocument()
    expect(screen.getByText('7 天内可无理由退款。')).toBeInTheDocument()
    expect(screen.getByText('质量分：92.5')).toBeInTheDocument()
    expect(screen.getByText('1 个问题')).toBeInTheDocument()
    expect(screen.getByText('缺少退款时效')).toBeInTheDocument()
    expect(screen.getByText('csv')).toBeInTheDocument()
  })

  it('无问题与元数据时展示无问题标签', () => {
    render(
      <CleanedDataDrawer item={{ ...ITEM, issues: [], metadata: null }} open onClose={() => {}} />
    )

    expect(screen.getByText('无问题')).toBeInTheDocument()
    expect(screen.queryByText('元数据')).toBeNull()
  })

  it('无数据时不渲染', () => {
    const { container } = render(<CleanedDataDrawer item={null} open onClose={() => {}} />)

    expect(container).toBeEmptyDOMElement()
  })
})
