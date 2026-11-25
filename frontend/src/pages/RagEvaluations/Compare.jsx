import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { LuArrowLeft, LuArrowLeftRight, LuDownload, LuFileText, LuRefreshCw } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageHeader } from '../../components/common/PageHeader'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Select } from '../../components/Select'
import { Table } from '../../components/Table'
import { JudgeNoiseNotice } from '../../components/rag/JudgeNoiseNotice'
import { RagBetaNotice } from '../../components/rag/RagBetaNotice'
import { ComparisonReportModal } from '../../components/reports/ComparisonReportModal'
import {
  useAllDatasetItemsQuery,
  useRagEvaluationQuery,
  useAllRagEvaluationResultsQuery,
  useRagEvaluationsQuery,
} from '../../hooks/useRagEvaluations'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { formatDateTime } from '../../lib/format'
import {
  buildCompareExportFilename,
  buildCompareExportPayload,
  buildComparisonReportPayload,
  downloadTextFile,
  toCompareCsv,
} from '../../lib/ragCompareExport'
import {
  caseDiffMeta,
  classifyCaseDiff,
  countCaseDiff,
  formatScore,
  groupResultsByItem,
  isSameConfigComparison,
  itemDisplayLabel,
  metricComparisonRows,
  metricShort,
  shortId,
} from '../../lib/ragEvaluation'

const MAX_RESULT_ROWS = 1000
const MAX_COMPARE_CASES = 200

const COUNT_ROWS = [
  ['已评分', 'evaluated_items'],
  ['invalid', 'invalid_items'],
  ['失败', 'failed_items'],
  ['跳过', 'skipped_items'],
  ['未处理', 'unprocessed_items'],
]

function deltaClass(delta) {
  if (typeof delta !== 'number' || delta === 0) return 'text-gray-500'
  return delta > 0 ? 'text-success-700' : 'text-error-700'
}

function formatDelta(delta) {
  if (typeof delta !== 'number' || !Number.isFinite(delta)) return '—'
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toFixed(3)}`
}

export default function RagEvaluationCompare() {
  const [params, setParams] = useSearchParams()
  const [reportOpen, setReportOpen] = useState(false)
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const baseId = params.get('base') || ''
  const targetId = params.get('target') || ''

  const runsQuery = useRagEvaluationsQuery({ status: 'completed', limit: 100 })
  const completedRuns = useMemo(() => runsQuery.data?.items || [], [runsQuery.data])

  const baseQuery = useRagEvaluationQuery(baseId)
  const targetQuery = useRagEvaluationQuery(targetId)
  const base = baseQuery.data
  const target = targetQuery.data

  const baseResultsQuery = useAllRagEvaluationResultsQuery(
    baseId,
    { maxRows: MAX_RESULT_ROWS },
    { enabled: Boolean(baseId) }
  )
  const targetResultsQuery = useAllRagEvaluationResultsQuery(
    targetId,
    { maxRows: MAX_RESULT_ROWS },
    { enabled: Boolean(targetId) }
  )
  const baseItemsQuery = useAllDatasetItemsQuery(
    base?.dataset_id,
    base?.dataset_version_id,
    { maxRows: MAX_RESULT_ROWS },
    { enabled: Boolean(base?.dataset_id && base?.dataset_version_id) }
  )
  const targetItemsQuery = useAllDatasetItemsQuery(
    target?.dataset_id,
    target?.dataset_version_id,
    { maxRows: MAX_RESULT_ROWS },
    { enabled: Boolean(target?.dataset_id && target?.dataset_version_id) }
  )

  useEffect(() => {
    if (!baseId || targetId) return
    const candidate = completedRuns.find(run => run.id !== baseId)
    if (candidate) {
      setParams({ base: baseId, target: candidate.id }, { replace: true })
    }
  }, [baseId, targetId, completedRuns, setParams])

  const options = useMemo(
    () =>
      completedRuns.map(run => ({
        label: `${run.dataset_name} · ${shortId(run.id)}`,
        value: run.id,
      })),
    [completedRuns]
  )

  const itemMap = useMemo(() => {
    const map = new Map()
    for (const item of baseItemsQuery.data?.items || []) map.set(item.id, item)
    for (const item of targetItemsQuery.data?.items || []) map.set(item.id, item)
    return map
  }, [baseItemsQuery.data, targetItemsQuery.data])

  const { rows, diffCounts, alignedCount, caseTruncated } = useMemo(() => {
    const baseMap = new Map(
      groupResultsByItem(baseResultsQuery.data?.items || []).map(item => [item.itemId, item])
    )
    const targetMap = new Map(
      groupResultsByItem(targetResultsQuery.data?.items || []).map(item => [item.itemId, item])
    )
    const ids = new Set([...baseMap.keys(), ...targetMap.keys()])
    const built = [...ids]
      .map(itemId => {
        const baseCase = baseMap.get(itemId)
        const targetCase = targetMap.get(itemId)
        const item = itemMap.get(itemId)
        return {
          itemId,
          item,
          baseCase,
          targetCase,
          diff: classifyCaseDiff(baseCase, targetCase),
          linkRunId: targetCase ? targetId : baseId,
        }
      })
      .sort((left, right) =>
        String(itemDisplayLabel(left.item)).localeCompare(
          String(itemDisplayLabel(right.item)),
          'zh-CN'
        )
      )
    const displayed = built.slice(0, MAX_COMPARE_CASES)
    return {
      rows: displayed,
      diffCounts: countCaseDiff(displayed),
      alignedCount: built.length,
      caseTruncated: built.length > MAX_COMPARE_CASES,
    }
  }, [baseResultsQuery.data, targetResultsQuery.data, itemMap, baseId, targetId])

  const metricRows = metricComparisonRows(base?.aggregate, target?.aggregate)
  const baseLoaded = baseResultsQuery.data?.loaded ?? 0
  const baseTotal = baseResultsQuery.data?.total ?? 0
  const targetLoaded = targetResultsQuery.data?.loaded ?? 0
  const targetTotal = targetResultsQuery.data?.total ?? 0
  const resultsTruncated = Boolean(
    baseResultsQuery.data?.truncated || targetResultsQuery.data?.truncated
  )
  const sameRun = Boolean(baseId && targetId && baseId === targetId)
  const versionMismatch = Boolean(
    base && target && base.dataset_version_id !== target.dataset_version_id
  )
  const datasetMismatch = Boolean(base && target && base.dataset_id !== target.dataset_id)
  const sameConfig = isSameConfigComparison(base, target)

  const exportDisabled =
    !base ||
    !target ||
    rows.length === 0 ||
    baseResultsQuery.isLoading ||
    targetResultsQuery.isLoading ||
    baseItemsQuery.isLoading ||
    targetItemsQuery.isLoading

  const handleExport = format => {
    const payload = buildCompareExportPayload({
      base,
      target,
      metricRows,
      rows,
      diffCounts,
      alignedCount,
      caseTruncated,
      maxCases: MAX_COMPARE_CASES,
    })
    const filename = buildCompareExportFilename(format, baseId, targetId, payload.exported_at)
    if (format === 'csv') {
      downloadTextFile(filename, toCompareCsv(payload), 'text/csv;charset=utf-8')
      return
    }
    downloadTextFile(
      filename,
      `${JSON.stringify(payload, null, 2)}\n`,
      'application/json;charset=utf-8'
    )
  }

  const reportComparison = useMemo(() => {
    if (!base || !target || rows.length === 0) return null
    return buildComparisonReportPayload({
      base,
      target,
      metricRows,
      rows,
      diffCounts,
      alignedCount,
      caseTruncated,
      maxCases: MAX_COMPARE_CASES,
      compareUrl: `/rag-evaluations/compare?base=${baseId}&target=${targetId}`,
    })
  }, [base, target, metricRows, rows, diffCounts, alignedCount, caseTruncated, baseId, targetId])

  const loading =
    runsQuery.isLoading ||
    (Boolean(baseId) && baseQuery.isLoading) ||
    (Boolean(targetId) && targetQuery.isLoading)

  if (loading) {
    return <AsyncState loading />
  }

  if (runsQuery.isError || baseQuery.isError || targetQuery.isError) {
    return (
      <AsyncState
        error={runsQuery.error || baseQuery.error || targetQuery.error}
        onRetry={() => {
          runsQuery.refetch()
          baseQuery.refetch()
          targetQuery.refetch()
        }}
      />
    )
  }

  if (completedRuns.length < 2) {
    return (
      <section className="space-y-6">
        <PageHeader index="05" eyebrow="RAG Evaluation" title="Run 对比" />
        <Empty
          title="至少需要两个 completed Run"
          description="先运行两次评测（同一数据集版本），再回来对比。"
          action={
            <Link to="/rag-evaluations" className="text-sm text-primary-600">
              返回 Run 列表
            </Link>
          }
        />
      </section>
    )
  }

  const caseColumns = [
    {
      key: 'case',
      title: 'Case',
      dataIndex: 'itemId',
      render: (value, record) => (
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-gray-900">
            {itemDisplayLabel(record.item)}
          </p>
          <p className="mt-0.5 truncate text-[11px] text-gray-500">
            {record.item?.query || `item ${shortId(value)}`}
          </p>
        </div>
      ),
    },
    ...['faithfulness', 'answer_correctness', 'answer_relevancy'].map(metric => ({
      key: metric,
      title: metricShort(metric),
      render: (_, record) => {
        const row = (record.diff.deltas || []).find(item => item.name === metric)
        if (!row || (row.base === null && row.target === null)) {
          return <span className="text-xs text-gray-400">—</span>
        }
        return (
          <div className="text-xs">
            <span className="text-gray-600">
              {formatScore(row.base, 2)} → {formatScore(row.target, 2)}
            </span>
            <span className={`ml-1 font-medium ${deltaClass(row.delta)}`}>
              {formatDelta(row.delta)}
            </span>
          </div>
        )
      },
    })),
    {
      key: 'status',
      title: '分类',
      render: (_, record) => {
        const meta = caseDiffMeta(record.diff.status)
        return (
          <Badge variant={meta.variant} size="sm">
            {meta.label}
          </Badge>
        )
      },
    },
    {
      key: 'note',
      title: '说明',
      render: (_, record) => (
        <span className="text-[11px] text-gray-500">{record.diff.note || '—'}</span>
      ),
    },
    {
      key: 'actions',
      title: '操作',
      render: (_, record) => (
        <Link
          to={`/rag-evaluations/${record.linkRunId}/cases/${record.itemId}`}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          查看 Case
        </Link>
      ),
    },
  ]

  return (
    <section className="space-y-6">
      <div>
        <Link
          to="/rag-evaluations"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <LuArrowLeft className="h-4 w-4" aria-hidden="true" />
          返回 Run 列表
        </Link>
      </div>

      <PageHeader
        index="05"
        eyebrow="RAG Evaluation"
        title="Run 对比"
        description="同一数据集版本下，比较两个 completed Run 的指标与 Case 变化。只读，不改 target。"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              icon={<LuDownload className="h-4 w-4" />}
              onClick={() => handleExport('csv')}
              disabled={exportDisabled}
            >
              导出 CSV
            </Button>
            <Button
              variant="outline"
              icon={<LuDownload className="h-4 w-4" />}
              onClick={() => handleExport('json')}
              disabled={exportDisabled}
            >
              导出 JSON
            </Button>
            <Button
              variant="outline"
              icon={<LuFileText className="h-4 w-4" />}
              onClick={() => setReportOpen(true)}
              disabled={!reportComparison || !currentDatasourceId}
              title={currentDatasourceId ? undefined : '请先在顶部「数据源选择器」中选择数据源'}
            >
              生成报告
            </Button>
            <Button
              variant="outline"
              icon={<LuRefreshCw className="h-4 w-4" />}
              onClick={() => {
                runsQuery.refetch()
                baseQuery.refetch()
                targetQuery.refetch()
                baseResultsQuery.refetch()
                targetResultsQuery.refetch()
              }}
            >
              刷新
            </Button>
          </div>
        }
      />

      <RagBetaNotice />
      <JudgeNoiseNotice sameConfig={sameConfig} />

      <div className="grid gap-3 rounded-md border border-gray-200 bg-white p-4 md:grid-cols-[1fr_auto_1fr]">
        <div>
          <p className="mb-1 text-xs font-medium text-gray-600">Base Run</p>
          <Select
            options={options.filter(option => option.value !== targetId)}
            value={baseId}
            onChange={value =>
              setParams({ base: value, ...(targetId ? { target: targetId } : {}) })
            }
            placeholder="选择 Base Run"
            searchable
            ariaLabel="Base Run"
          />
          {base ? (
            <p className="mt-1 text-[11px] text-gray-500">
              {base.dataset_name} · 版本 {shortId(base.dataset_version_id)} ·{' '}
              {formatDateTime(base.completed_at)}
            </p>
          ) : null}
        </div>
        <div className="flex items-end justify-center pb-1">
          <Button
            variant="outline"
            icon={<LuArrowLeftRight className="h-4 w-4" />}
            onClick={() => setParams({ base: targetId, target: baseId }, { replace: true })}
            disabled={!baseId || !targetId}
          >
            交换
          </Button>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-gray-600">Target Run</p>
          <Select
            options={options.filter(option => option.value !== baseId)}
            value={targetId}
            onChange={value => setParams({ base: baseId, target: value })}
            placeholder="选择 Target Run"
            searchable
            ariaLabel="Target Run"
          />
          {target ? (
            <p className="mt-1 text-[11px] text-gray-500">
              {target.dataset_name} · 版本 {shortId(target.dataset_version_id)} ·{' '}
              {formatDateTime(target.completed_at)}
            </p>
          ) : null}
        </div>
      </div>

      {sameRun ? (
        <p
          role="alert"
          className="rounded border border-error-500/30 bg-error-50 p-3 text-sm text-error-700"
        >
          请选择两个不同的 Run。
        </p>
      ) : null}

      {versionMismatch ? (
        <p
          role="alert"
          className="rounded border border-warning-500/30 bg-warning-50 p-3 text-sm text-warning-800"
        >
          Base 与 Target 的{datasetMismatch ? '数据集和' : ''}版本不一致 （
          {shortId(base?.dataset_version_id)} vs {shortId(target?.dataset_version_id)}）。 Case
          对齐可能不完整，delta 仅供参考。
        </p>
      ) : null}

      {!baseId || !targetId ? (
        <Empty
          title="选择两个 Run 开始对比"
          description="Base 与 Target 都必须是 completed Run；优先使用同一数据集版本。"
        />
      ) : sameRun ? null : (
        <>
          <div className="rounded-md border border-gray-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-gray-900">指标对比</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-[11px] uppercase tracking-wide text-gray-400">
                    <th className="py-2 pr-3">指标</th>
                    <th className="py-2 pr-3">Base</th>
                    <th className="py-2 pr-3">Target</th>
                    <th className="py-2">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {metricRows.map(row => (
                    <tr key={row.name} className="border-b border-gray-100">
                      <td className="py-2 pr-3 text-xs text-gray-700">
                        {row.short} / {row.label}
                      </td>
                      <td className="py-2 pr-3">{formatScore(row.base, 3)}</td>
                      <td className="py-2 pr-3">{formatScore(row.target, 3)}</td>
                      <td className={`py-2 font-medium ${deltaClass(row.delta)}`}>
                        {formatDelta(row.delta)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-md border border-gray-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-gray-900">样本状态</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-[11px] uppercase tracking-wide text-gray-400">
                    <th className="py-2 pr-3">项</th>
                    <th className="py-2 pr-3">Base</th>
                    <th className="py-2 pr-3">Target</th>
                    <th className="py-2">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {COUNT_ROWS.map(([label, key]) => {
                    const baseValue = base?.[key] ?? 0
                    const targetValue = target?.[key] ?? 0
                    const delta = targetValue - baseValue
                    return (
                      <tr key={key} className="border-b border-gray-100">
                        <td className="py-2 pr-3 text-xs text-gray-700">{label}</td>
                        <td className="py-2 pr-3">{baseValue}</td>
                        <td className="py-2 pr-3">{targetValue}</td>
                        <td className={`py-2 font-medium ${deltaClass(delta)}`}>
                          {delta > 0 ? `+${delta}` : delta}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-500">Case diff：</span>
            {Object.entries(diffCounts).map(([status, count]) => {
              const meta = caseDiffMeta(status)
              return (
                <Badge key={status} variant={meta.variant} size="sm">
                  {meta.label} {count}
                </Badge>
              )
            })}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Case 级变化</h2>
              <p className="text-xs text-gray-500">
                按 dataset_item_id 对齐；F/C/R 各自比较，分类取绝对变化最大的指标。
              </p>
            </div>
            <p className="mb-2 text-xs text-gray-500">
              结果加载：Base {baseLoaded}/{baseTotal} · Target {targetLoaded}/{targetTotal}
              {resultsTruncated ? `（每侧最多 ${MAX_RESULT_ROWS} 行，已截断）` : ''}
            </p>
            {caseTruncated ? (
              <p
                role="alert"
                className="mb-2 rounded border border-warning-500/30 bg-warning-50 p-2 text-xs text-warning-800"
              >
                仅对比前 {MAX_COMPARE_CASES} 个 Case（对齐后共 {alignedCount} 个）。
              </p>
            ) : null}
            <AsyncState
              loading={baseResultsQuery.isLoading || targetResultsQuery.isLoading}
              error={baseResultsQuery.error || targetResultsQuery.error}
              onRetry={() => {
                baseResultsQuery.refetch()
                targetResultsQuery.refetch()
              }}
            >
              {rows.length === 0 ? (
                <Empty
                  title="没有可对齐的 Case"
                  description="两个 Run 的结果为空，或结果尚未落库。"
                />
              ) : (
                <Table
                  columns={caseColumns}
                  dataSource={rows}
                  rowKey="itemId"
                  caption="Run 对比 Case diff"
                />
              )}
            </AsyncState>
          </div>
        </>
      )}

      <ComparisonReportModal
        open={reportOpen}
        onClose={() => setReportOpen(false)}
        datasourceId={currentDatasourceId}
        comparison={reportComparison}
      />
    </section>
  )
}
