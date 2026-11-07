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

const AXIS_TICK = { fill: '#7C776A', fontSize: 10, fontFamily: 'monospace' }
const AXIS_LINE = { stroke: '#E7E2D6' }
const GRID_STROKE = '#E7E2D6'
const TOOLTIP_STYLE = {
  background: '#FAF8F3',
  border: '1px solid #E7E2D6',
  borderRadius: 0,
  fontSize: 12,
  fontFamily: 'monospace',
  color: '#17160F',
  boxShadow: 'none',
}
const LEGEND_STYLE = {
  fontSize: 10,
  fontFamily: 'monospace',
  letterSpacing: '0.08em',
  color: '#7C776A',
  paddingTop: 8,
}

/**
 * 图表容器（编辑部风格）：细线坐标、点状网格、朱砂主色、环形饼图。
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
      className={clsx('border border-gray-200 bg-white p-5', className)}
    >
      <header className="mb-4 flex items-baseline justify-between gap-2 border-b border-gray-100 pb-3">
        <h3 className="font-display text-lg font-normal tracking-tight text-gray-900">{title}</h3>
        {showActions ? (
          <div className="flex items-center gap-1">
            {onRefresh ? (
              <Button
                size="sm"
                variant="ghost"
                aria-label="刷新图表"
                icon={<LuRefreshCw className="h-3.5 w-3.5" />}
                onClick={onRefresh}
              />
            ) : null}
            {onExport ? (
              <Button
                size="sm"
                variant="ghost"
                aria-label="导出图表"
                icon={<LuDownload className="h-3.5 w-3.5" />}
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
                <Pie
                  data={data}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="54%"
                  outerRadius="76%"
                  paddingAngle={2}
                  stroke="#FAF8F3"
                  strokeWidth={2}
                >
                  {data.map((entry, index) => (
                    <Cell key={entry.name || index} fill={PALETTE[index % PALETTE.length]} />
                  ))}
                </Pie>
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                {showLegend ? <Legend wrapperStyle={LEGEND_STYLE} /> : null}
              </PieChart>
            ) : type === 'bar' ? (
              <BarChart data={data} barCategoryGap="28%">
                <CartesianGrid stroke={GRID_STROKE} strokeDasharray="2 6" vertical={false} />
                <XAxis dataKey="name" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={32} />
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(23,22,15,0.03)' }} />
                {showLegend ? <Legend wrapperStyle={LEGEND_STYLE} /> : null}
                <Bar dataKey="value" fill="var(--chart-primary)" radius={[0, 0, 0, 0]} />
              </BarChart>
            ) : type === 'area' ? (
              <AreaChart data={data}>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--chart-primary)" stopOpacity={0.18} />
                    <stop offset="100%" stopColor="var(--chart-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={GRID_STROKE} strokeDasharray="2 6" vertical={false} />
                <XAxis dataKey="name" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={32} />
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                {showLegend ? <Legend wrapperStyle={LEGEND_STYLE} /> : null}
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="var(--chart-primary)"
                  strokeWidth={1.5}
                  fill={`url(#${gradientId})`}
                />
              </AreaChart>
            ) : (
              <LineChart data={data}>
                <CartesianGrid stroke={GRID_STROKE} strokeDasharray="2 6" vertical={false} />
                <XAxis dataKey="name" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={32} />
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                {showLegend ? <Legend wrapperStyle={LEGEND_STYLE} /> : null}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="var(--chart-primary)"
                  strokeWidth={1.5}
                  dot={false}
                  activeDot={{ r: 3, fill: 'var(--chart-primary)', stroke: '#FAF8F3', strokeWidth: 2 }}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
