import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { KnowledgeEntryCard } from './KnowledgeEntryCard'

const ENTRY = {
  id: 'f1',
  question: '如何退款？',
  answer: '7 天内可无理由退款。',
  category: '售后',
  tags: ['退款', '售后', '流程', '时效'],
  confidence: 0.95,
  quality_score: 88,
  frequency: 12,
  source: 'extracted',
  created_at: '2026-10-24T10:00:00Z',
}

describe('KnowledgeEntryCard', () => {
  it('展示问题/答案/分类/标签/元信息', () => {
    render(<KnowledgeEntryCard entry={ENTRY} />)

    expect(screen.getByRole('heading', { name: '如何退款？' })).toBeInTheDocument()
    expect(screen.getByText('7 天内可无理由退款。')).toBeInTheDocument()
    expect(screen.getAllByText('售后').length).toBeGreaterThan(0)
    expect(screen.getByText('+1')).toBeInTheDocument()
    expect(screen.getByText('95%')).toBeInTheDocument()
    expect(screen.getByText('88.0')).toBeInTheDocument()
    expect(screen.getByText('提取')).toBeInTheDocument()
  })

  it('搜索态展示相似度', () => {
    render(<KnowledgeEntryCard entry={ENTRY} searchSimilarity={0.91} />)

    expect(screen.getByText('相似度 91%')).toBeInTheDocument()
  })

  it('编辑与删除回调', async () => {
    const onEdit = vi.fn()
    const onDelete = vi.fn()
    const user = userEvent.setup()
    render(<KnowledgeEntryCard entry={ENTRY} onEdit={onEdit} onDelete={onDelete} />)

    await user.click(screen.getByRole('button', { name: '编辑' }))
    expect(onEdit).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: '删除' }))
    await user.click(await screen.findByRole('button', { name: '确认' }))
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('无写权限时不展示编辑/删除', () => {
    render(<KnowledgeEntryCard entry={ENTRY} canWrite={false} />)

    expect(screen.queryByRole('button', { name: '编辑' })).toBeNull()
    expect(screen.queryByRole('button', { name: '删除' })).toBeNull()
  })
})
