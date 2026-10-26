import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Chart } from './Chart'

vi.mock('recharts', () => {
  const Mock = ({ children }) => <div data-testid="recharts">{children}</div>
  return {
    ResponsiveContainer: Mock,
    LineChart: Mock,
    BarChart: Mock,
    AreaChart: Mock,
    PieChart: Mock,
    Line: () => null,
    Bar: () => null,
    Area: () => null,
    Pie: ({ children }) => <div>{children}</div>,
    Cell: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
  }
})

const DATA = [
  { name: '10-20', value: 10 },
  { name: '10-21', value: 20 },
]

describe('Chart', () => {
  it('无数据时展示空态', () => {
    render(<Chart title="处理量趋势" data={[]} />)

    expect(screen.getByRole('region', { name: '处理量趋势' })).toBeInTheDocument()
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
  })

  it('loading 时展示骨架', () => {
    render(<Chart title="趋势" data={DATA} loading />)

    expect(document.querySelector('.animate-pulse')).not.toBeNull()
    expect(screen.queryByTestId('recharts')).toBeNull()
  })

  it.each(['line', 'bar', 'area', 'pie'])('%s 类型渲染图表', type => {
    render(<Chart title={`${type} 图`} type={type} data={DATA} />)

    expect(screen.getAllByTestId('recharts').length).toBeGreaterThan(0)
  })

  it('提供读屏可读的隐藏数据表', () => {
    render(<Chart title="处理量趋势" data={DATA} />)

    expect(screen.getByRole('table', { name: '处理量趋势数据表' })).toBeInTheDocument()
    expect(screen.getByRole('rowheader', { name: '10-20' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '10' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '20' })).toBeInTheDocument()
  })

  it('工具栏回调', async () => {
    const onRefresh = vi.fn()
    const onExport = vi.fn()
    const user = userEvent.setup()
    render(<Chart title="趋势" data={DATA} onRefresh={onRefresh} onExport={onExport} />)

    await user.click(screen.getByRole('button', { name: '刷新图表' }))
    await user.click(screen.getByRole('button', { name: '导出图表' }))

    expect(onRefresh).toHaveBeenCalledTimes(1)
    expect(onExport).toHaveBeenCalledTimes(1)
  })
})
