import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DataSourceCard } from './DataSourceCard'

const DATASOURCE = {
  id: 'ds-1',
  name: '客服对话-2026年1月',
  type: 'customer_service',
  status: 'active',
  statistics: {
    total_records: 12345,
    cleaned_records: 12000,
    quality_score_avg: 85.5,
    last_processed_at: '2026-10-24T10:30:00Z',
  },
}

describe('DataSourceCard', () => {
  it('展示名称、状态、类型与统计信息', () => {
    render(<DataSourceCard datasource={DATASOURCE} />)

    expect(screen.getByRole('heading', { name: '客服对话-2026年1月' })).toBeInTheDocument()
    expect(screen.getByText('已就绪')).toBeInTheDocument()
    expect(screen.getByText('客服对话')).toBeInTheDocument()
    expect(screen.getByText('12345 条')).toBeInTheDocument()
    expect(screen.getByText('12000 条')).toBeInTheDocument()
    expect(screen.getByText('85.5')).toBeInTheDocument()
  })

  it('无统计数据时显示默认值', () => {
    render(<DataSourceCard datasource={{ ...DATASOURCE, statistics: null }} />)

    expect(screen.getAllByText('0 条').length).toBe(2)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('异常状态渲染红色徽章', () => {
    render(<DataSourceCard datasource={{ ...DATASOURCE, status: 'error' }} />)

    expect(screen.getByText('异常')).toBeInTheDocument()
  })

  it('渲染 actions 插槽', () => {
    render(<DataSourceCard datasource={DATASOURCE} actions={<button type="button">操作</button>} />)

    expect(screen.getByRole('button', { name: '操作' })).toBeInTheDocument()
  })
})
