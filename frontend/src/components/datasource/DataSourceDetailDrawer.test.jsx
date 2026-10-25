import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DataSourceDetailDrawer } from './DataSourceDetailDrawer'

const DATASOURCE = {
  id: 'ds-1',
  name: '客服对话-2026年1月',
  description: '1 月批次',
  type: 'customer_service',
  status: 'active',
  config: {
    auto_clean: true,
    auto_evaluate: false,
    evaluation_dimensions: ['accuracy', 'completeness'],
  },
  statistics: {
    total_records: 1234,
    cleaned_records: 1000,
    quality_score_avg: 85.5,
    last_processed_at: '2026-10-24T10:30:00Z',
  },
  created_at: '2026-10-20T08:00:00Z',
  updated_at: '2026-10-24T10:30:00Z',
}

describe('DataSourceDetailDrawer', () => {
  it('展示名称、状态、类型与描述', () => {
    render(<DataSourceDetailDrawer datasource={DATASOURCE} open onClose={() => {}} />)

    expect(screen.getByRole('dialog', { name: '数据源详情' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '客服对话-2026年1月' })).toBeInTheDocument()
    expect(screen.getByText('已就绪')).toBeInTheDocument()
    expect(screen.getByText('1 月批次')).toBeInTheDocument()
  })

  it('按统计派生处理进度', () => {
    render(<DataSourceDetailDrawer datasource={DATASOURCE} open onClose={() => {}} />)

    const progress = screen.getByRole('region', { name: '处理进度' })
    expect(progress).toHaveTextContent('已上传')
    expect(progress).toHaveTextContent('已清洗')
    expect(progress).toHaveTextContent('已评估')
    expect(progress).not.toHaveTextContent('workflow_status')
  })

  it('展示统计与配置', () => {
    render(<DataSourceDetailDrawer datasource={DATASOURCE} open onClose={() => {}} />)

    expect(screen.getByText('1,234 条')).toBeInTheDocument()
    expect(screen.getByText('85.5')).toBeInTheDocument()
    expect(screen.getByText('开启')).toBeInTheDocument()
    expect(screen.getByText('accuracy、completeness')).toBeInTheDocument()
  })

  it('无数据源时不渲染', () => {
    const { container } = render(
      <DataSourceDetailDrawer datasource={null} open onClose={() => {}} />
    )

    expect(container).toBeEmptyDOMElement()
  })
})
