import { useId } from 'react'
import clsx from 'clsx'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LuDownload, LuRefreshCw } from 'react-icons/lu'
import { Button } from '../Button'
import { Empty } from '../Empty'
import { Skeleton } from '../Skeleton'

const PALETTE = [
  'var(--chart-primary)',
  'var(--chart-success)',
  'var(--chart-warning)',
  'var(--chart-info)',
  'var(--chart-error)',
]

/**
 * 图表容器（02 §3.4）：line / bar / pie / area，带加载/空态/工具栏。
 * @param {{
 *   title: string,
 *   type?: 'line'|'bar'|'pie'|'area',
 *   data?: Object[],
 *   loading?: boolean,
 *   height?: number,
 *   showLegend?: boolean,
 *   showToolbar?: boolean,
 *   onRefresh?: () => void,
 *   onExport?: () => void,
 *   emptyText?: string,
 *   className?: string,
 * }} props
 */
export function Chart({
  title,
  type = 'line',
  data = [],
  loading = false,
  height = 300,
  showLegend = true,
  showToolbar = true,
  onRefresh,
  onExport,
  emptyText = '暂无数据',
  className,
}) {
  const gradientId = `chart-gradient-${String(useId()).replace(/:/g, '')}`
  const hasData = Array.isArray(data) && data.length > 0
  const showActions = showToolbar && (onRefresh || onExport)

  return (
    <section
      aria-label={title}
      className={clsx('rounded-md border border-gray-200 bg-white p-4', className)}
    >
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {showActions ? (
          <div className="flex items-center gap-1">
            {onRefresh ? (
              <Button
                size="sm"
                variant="ghost"
                aria-label="刷新图表"
                icon={<LuRefreshCw className="h-4 w-4" />}
                onClick={onRefresh}
              />
            ) : null}
            {onExport ? (
              <Button
                size="sm"
                variant="ghost"
                aria-label="导出图表"
                icon={<LuDownload className="h-4 w-4" />}
                onClick={onExport}
              />
            ) : null}
          </div>
        ) : null}
      </header>

      {hasData && !loading ? (
        // 读屏替代：SVG 数据点不可聚焦，用隐藏表格提供等价的文本数据
        <table className="sr-only">
          <caption>{title}数据表</caption>
          <thead>
            <tr>
              <th scope="col">名称</th>
              <th scope="col">数值</th>
            </tr>
          </thead>
          <tbody>
            {data.map((entry, index) => (
              <tr key={String(entry.name ?? index)}>
                <th scope="row">{String(entry.name ?? '')}</th>
                <td>{String(entry.value ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {loading ? (
        <Skeleton variant="card" />
      ) : !hasData ? (
        <Empty title={emptyText} description="数据接入后展示" />
      ) : (
        <div className="w-full" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            {type === 'pie' ? (
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" outerRadius="70%">
                  {data.map((entry, index) => (
                    <Cell key={entry.name || index} fill={PALETTE[index % PALETTE.length]} />
                  ))}
                </Pie>
                <RechartsTooltip />
                {showLegend ? <Legend /> : null}
              </PieChart>
            ) : type === 'bar' ? (
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid, #E5E7EB)" />
                <XAxis dataKey="name" />
                <YAxis />
                <RechartsTooltip />
                {showLegend ? <Legend /> : null}
                <Bar dataKey="value" fill="var(--chart-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            ) : type === 'area' ? (
              <AreaChart data={data}>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--chart-primary)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--chart-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="name" />
                <YAxis />
                <RechartsTooltip />
                {showLegend ? <Legend /> : null}
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="var(--chart-primary)"
                  fill={`url(#${gradientId})`}
                />
              </AreaChart>
            ) : (
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="name" />
                <YAxis />
                <RechartsTooltip />
                {showLegend ? <Legend /> : null}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="var(--chart-primary)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
