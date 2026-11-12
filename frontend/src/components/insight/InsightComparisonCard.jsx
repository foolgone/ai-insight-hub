import { useMemo, useState } from 'react'
import { Badge } from '../Badge'
import { Empty } from '../Empty'
import { Select } from '../Select'
import { AsyncState } from '../common/AsyncState'
import { useInsightRunComparisonQuery, useQualityRunsQuery } from '../../hooks/useQuality'
import { formatDateTime } from '../../lib/format'

const SENTIMENT_LABELS = ['正面', '中性', '负面']

function formatPercent(value) {
  const num = Number(value) || 0
  // 兼容 0-1 与 0-100 两种口径
  return num <= 1 ? `${Math.round(num * 1000) / 10}%` : `${Math.round(num * 10) / 10}%`
}

function formatDelta(value, suffix = '') {
  const num = Number(value) || 0
  if (Math.abs(num) < 0.0001) return <span className="text-gray-500">持平</span>
  return (
    <span className={num > 0 ? 'text-success-600' : 'text-error-600'}>
      {num > 0 ? '+' : ''}
      {Math.round(num * 1000) / 1000}
      {suffix}
    </span>
  )
}

function runLabel(run) {
  return `${formatDateTime(run.completed_at || run.created_at)} · ${run.status}`
}

/**
 * 洞察批次对比（#3）：两次 analyze 任务的情感分布 / 意图分布 / 痛点增减。
 *
 * 洞察原本只有「最近一次」，这里补上「改完之后变在哪」。
 *
 * @param {{ datasourceId?: string|null }} props
 */
export function InsightComparisonCard({ datasourceId = null }) {
  const [baseId, setBaseId] = useState(null)
  const [targetId, setTargetId] = useState(null)

  const runsQuery = useQualityRunsQuery(datasourceId, { task_type: 'analyze' })
  const runs = useMemo(
    () => (runsQuery.data?.items || []).filter(run => run.status === 'completed'),
    [runsQuery.data]
  )
  const options = useMemo(
    () => runs.map(run => ({ value: run.task_id, label: runLabel(run) })),
    [runs]
  )

  const effectiveTarget = targetId ?? runs[0]?.task_id ?? null
  const effectiveBase = baseId ?? runs[1]?.task_id ?? null
  const compareQuery = useInsightRunComparisonQuery(datasourceId, effectiveBase, effectiveTarget)

  if (!datasourceId) return null
  // 少于两次洞察分析时不展示（避免空卡片）
  if (!runsQuery.isLoading && runs.length < 2) return null

  return (
    <div className="border border-gray-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-normal text-gray-900">洞察对比</h2>
          <p className="mt-1 text-xs text-gray-500">
            对比两次洞察分析：情感占比、意图分布与痛点增减（「对比」相对「基线」）。
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-52">
            <span className="mb-1 block text-xs font-medium text-gray-600">基线</span>
            <Select
              options={options}
              value={effectiveBase || undefined}
              onChange={setBaseId}
              placeholder="选择基线"
              ariaLabel="洞察基线"
            />
          </div>
          <div className="w-52">
            <span className="mb-1 block text-xs font-medium text-gray-600">对比</span>
            <Select
              options={options}
              value={effectiveTarget || undefined}
              onChange={setTargetId}
              placeholder="选择对比"
              ariaLabel="洞察对比"
            />
          </div>
        </div>
      </div>

      {runsQuery.isError ? (
        <p role="alert" className="mt-3 text-sm text-error-600">
          洞察批次加载失败
        </p>
      ) : compareQuery.isError ? (
        <AsyncState error={compareQuery.error} onRetry={() => compareQuery.refetch()} />
      ) : compareQuery.isLoading ? (
        <p className="mt-3 text-sm text-gray-500">正在对比...</p>
      ) : compareQuery.data ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-900">情感占比</h3>
            <ul className="space-y-1 text-sm text-gray-700">
              {compareQuery.data.sentiment.length === 0 ? (
                <li className="text-gray-500">本次洞察未输出情感分布</li>
              ) : (
                compareQuery.data.sentiment.map(item => (
                  <li key={item.name} className="flex items-center justify-between gap-2">
                    <span>{SENTIMENT_LABELS.includes(item.name) ? item.name : item.name}</span>
                    <span className="text-gray-500">
                      {formatPercent(item.base)} → {formatPercent(item.target)}
                    </span>
                    <span>{formatDelta(item.delta)}</span>
                  </li>
                ))
              )}
            </ul>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-900">意图分布（Top 8）</h3>
            <ul className="space-y-1 text-sm text-gray-700">
              {compareQuery.data.intents.length === 0 ? (
                <li className="text-gray-500">本次洞察未输出意图分布</li>
              ) : (
                compareQuery.data.intents.map(item => (
                  <li key={item.name} className="flex items-center justify-between gap-2">
                    <span className="truncate">{item.name}</span>
                    <span className="text-gray-500">
                      {item.base} → {item.target}
                    </span>
                    <span>{formatDelta(item.delta, ' 次')}</span>
                  </li>
                ))
              )}
            </ul>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-900">痛点变化</h3>
            <div className="space-y-2 text-sm">
              <div>
                <Badge variant="warning" size="sm">
                  新增 {compareQuery.data.pain_points_added.length}
                </Badge>
                <ul className="mt-1 list-inside list-disc text-gray-700">
                  {compareQuery.data.pain_points_added.slice(0, 5).map(item => (
                    <li key={item} className="truncate">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <Badge variant="success" size="sm">
                  消失 {compareQuery.data.pain_points_removed.length}
                </Badge>
                <ul className="mt-1 list-inside list-disc text-gray-700">
                  {compareQuery.data.pain_points_removed.slice(0, 5).map(item => (
                    <li key={item} className="truncate">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <Empty title="暂无洞察对比" description="同一数据源至少需要两次已完成的洞察分析。" />
      )}
    </div>
  )
}

export default InsightComparisonCard
