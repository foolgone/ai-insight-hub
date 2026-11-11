import { useMemo, useState } from 'react'
import { Badge } from '../Badge'
import { Empty } from '../Empty'
import { Select } from '../Select'
import { AsyncState } from '../common/AsyncState'
import { useQualityRunsQuery, useQualityRunComparisonQuery } from '../../hooks/useQuality'
import { formatDateTime } from '../../lib/format'

const DIMENSION_LABELS = {
  accuracy: '准确性',
  completeness: '完整性',
  hallucination: '幻觉控制',
  tone: '语气',
  compliance: '合规性',
}

const RUN_STATUS_LABELS = {
  completed: '已完成',
  running: '进行中',
  pending: '排队中',
  failed: '失败',
  cancelled: '已取消',
}

const BAND_LABELS = [
  { key: 'excellent', label: '优秀' },
  { key: 'good', label: '良好' },
  { key: 'fair', label: '合格' },
  { key: 'poor', label: '较差' },
]

/** 变化值：涨绿跌红、0 视为持平（阈值 0.01 避免浮点噪声）。 */
function Delta({ value, suffix = ' 分' }) {
  const num = Number(value) || 0
  if (Math.abs(num) < 0.01) {
    return <span className="text-gray-500">持平</span>
  }
  const positive = num > 0
  return (
    <span className={positive ? 'text-success-600' : 'text-error-600'}>
      {positive ? '+' : ''}
      {num.toFixed(1)}
      {suffix}
    </span>
  )
}

function formatScore(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(1) : '—'
}

function runOptionLabel(run) {
  const when = formatDateTime(run.completed_at || run.created_at)
  const status = RUN_STATUS_LABELS[run.status] || run.status
  if (!run.sample_count) return `${when} · ${status} · 无样本`
  return `${when} · 平均 ${formatScore(run.avg_overall_score)} · ${run.sample_count} 条`
}

/**
 * 批次对比（方向一：效果验证闭环）。
 *
 * 一次评估任务 = 一个批次；这里回答「同一批对话，改动前后变好了吗、变在哪」。
 * 历史批次（迁移 016 之前）没有 task_id 归属，接口会返回 409，面板给出提示。
 *
 * @param {{ datasourceId?: string|null }} props
 */
export function RunComparisonPanel({ datasourceId = null }) {
  const [baseId, setBaseId] = useState(null)
  const [targetId, setTargetId] = useState(null)

  const runsQuery = useQualityRunsQuery(datasourceId)
  const comparableRuns = useMemo(
    () => (runsQuery.data?.items || []).filter(run => run.sample_count > 0),
    [runsQuery.data]
  )
  const options = useMemo(
    () => comparableRuns.map(run => ({ value: run.task_id, label: runOptionLabel(run) })),
    [comparableRuns]
  )

  // 默认「最新一次 vs 上一次」；用户手动选择后以用户选择为准
  const effectiveTarget = targetId ?? comparableRuns[0]?.task_id ?? null
  const effectiveBase = baseId ?? comparableRuns[1]?.task_id ?? null

  const compareQuery = useQualityRunComparisonQuery(datasourceId, effectiveBase, effectiveTarget)
  const comparison = compareQuery.data

  if (!datasourceId) return null

  if (runsQuery.isError) {
    return <AsyncState error={runsQuery.error} onRetry={() => runsQuery.refetch()} />
  }

  if (comparableRuns.length < 2) {
    return (
      <Empty
        title="暂无可对比的批次"
        description="同一数据源至少需要两次已完成的评估（每次评估就是一个批次），才能比较改动前后的效果。"
      />
    )
  }

  return (
    <div className="space-y-4 rounded-md border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">批次对比</h2>
          <p className="mt-1 text-sm text-gray-600">
            对比两次评估的分数、维度、单条对话与问题变化；「对比」相对「基线」。
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-56">
            <span className="mb-1 block text-xs font-medium text-gray-600">基线（改动前）</span>
            <Select
              options={options}
              value={effectiveBase || undefined}
              onChange={setBaseId}
              placeholder="选择基线批次"
              ariaLabel="基线批次"
            />
          </div>
          <div className="w-56">
            <span className="mb-1 block text-xs font-medium text-gray-600">对比（改动后）</span>
            <Select
              options={options}
              value={effectiveTarget || undefined}
              onChange={setTargetId}
              placeholder="选择对比批次"
              ariaLabel="对比批次"
            />
          </div>
        </div>
      </div>

      {effectiveBase === effectiveTarget ? (
        <p
          role="status"
          className="rounded border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-700"
        >
          基线与对比不能是同一个批次，请重新选择。
        </p>
      ) : compareQuery.isError ? (
        <AsyncState error={compareQuery.error} onRetry={() => compareQuery.refetch()} />
      ) : compareQuery.isLoading ? (
        <p className="text-sm text-gray-500">正在对比...</p>
      ) : comparison ? (
        <ComparisonBody comparison={comparison} />
      ) : null}
    </div>
  )
}

function ComparisonBody({ comparison }) {
  const { base, target, delta } = comparison

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded border border-gray-200 p-3">
          <p className="text-xs text-gray-600">平均总分</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {formatScore(base.avg_overall_score)} → {formatScore(target.avg_overall_score)}
          </p>
          <p className="mt-1 text-sm">
            <Delta value={delta.avg_overall_score} />
          </p>
        </div>
        <div className="rounded border border-gray-200 p-3">
          <p className="text-xs text-gray-600">样本数</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {base.sample_count} → {target.sample_count}
          </p>
          <p className="mt-1 text-sm text-gray-600">
            {comparison.added_items || comparison.removed_items
              ? `新增 ${comparison.added_items} 条 / 消失 ${comparison.removed_items} 条`
              : '两侧样本一致'}
          </p>
        </div>
        <div className="rounded border border-gray-200 p-3">
          <p className="text-xs text-gray-600">待复核</p>
          <p className="mt-1 text-xl font-bold text-gray-900">
            {base.needs_review} → {target.needs_review}
          </p>
          <p className="mt-1 text-sm">
            <Delta value={delta.needs_review} suffix=" 条" />
          </p>
        </div>
        <div className="rounded border border-gray-200 p-3">
          <p className="text-xs text-gray-600">分数档位变化</p>
          <p className="mt-1 flex flex-wrap gap-2 text-sm">
            {BAND_LABELS.map(band => {
              const change = delta.bands?.[band.key] ?? 0
              return (
                <span key={band.key} className="inline-flex items-center gap-1">
                  <span className="text-gray-600">{band.label}</span>
                  <Delta value={change} suffix=" 条" />
                </span>
              )
            })}
          </p>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900">维度变化</h3>
        <table className="w-full text-sm">
          <caption className="sr-only">基线批次与对比批次的 5 维分数变化</caption>
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-600">
              <th scope="col" className="py-2 font-medium">
                维度
              </th>
              <th scope="col" className="py-2 font-medium">
                基线
              </th>
              <th scope="col" className="py-2 font-medium">
                对比
              </th>
              <th scope="col" className="py-2 font-medium">
                变化
              </th>
            </tr>
          </thead>
          <tbody>
            {comparison.dimensions.map(item => (
              <tr key={item.name} className="border-b border-gray-100">
                <td className="py-2 text-gray-800">{DIMENSION_LABELS[item.name] || item.name}</td>
                <td className="py-2 text-gray-700">{formatScore(item.base)}</td>
                <td className="py-2 text-gray-700">{formatScore(item.target)}</td>
                <td className="py-2">
                  <Delta value={item.delta} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <DialogueDeltaList
          title="退步最大的对话"
          items={comparison.regressions}
          emptyText="没有明显退步的对话（分差 ≥ 1 分）"
        />
        <DialogueDeltaList
          title="进步最大的对话"
          items={comparison.improvements}
          emptyText="没有明显进步的对话（分差 ≥ 1 分）"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <IssueDeltaList
          title="新增问题"
          items={comparison.issues_added}
          emptyText="没有新增问题文本"
          variant="warning"
        />
        <IssueDeltaList
          title="消失问题"
          items={comparison.issues_removed}
          emptyText="没有消失的问题文本"
          variant="success"
        />
      </div>

      <p className="text-xs text-gray-500">
        说明：问题文本是模型输出的自由文本，仅做去空白/大小写归一化后求差集，作为线索而非精确指标；
        历史批次（升级前产生）没有批次归属，无法参与对比。
      </p>
    </div>
  )
}

function DialogueDeltaList({ title, items = [], emptyText }) {
  return (
    <div className="rounded border border-gray-200 p-3">
      <h3 className="mb-2 text-sm font-semibold text-gray-900">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {items.map(item => (
            <li key={item.data_id} className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs text-gray-500">
                {String(item.data_id).slice(0, 8)}
              </span>
              <span className="text-gray-700">
                {formatScore(item.base_score)} → {formatScore(item.target_score)}
              </span>
              <Delta value={item.delta} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function IssueDeltaList({ title, items = [], emptyText, variant }) {
  return (
    <div className="rounded border border-gray-200 p-3">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-900">
        {title}
        <Badge variant={variant} size="sm">
          {items.length}
        </Badge>
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <ul className="list-inside list-disc space-y-1 text-sm text-gray-700">
          {items.map(item => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default RunComparisonPanel
