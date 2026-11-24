import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LuArrowLeft, LuFileText, LuRefreshCw } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Table } from '../../components/Table'
import { RagBetaNotice } from '../../components/rag/RagBetaNotice'
import {
  useDatasetItemsQuery,
  useRagEvaluationFailuresQuery,
  useRagEvaluationQuery,
  useRagEvaluationResultsQuery,
} from '../../hooks/useRagEvaluations'
import { formatDateTime } from '../../lib/format'
import {
  caseKnownIssue,
  formatPercent,
  formatScore,
  groupResultsByItem,
  invalidReasonLabel,
  itemDisplayLabel,
  judgeMetricRows,
  metricLabel,
  metricShort,
  resultStatusMeta,
  runKnownIssues,
  runStatusMeta,
  shortId,
} from '../../lib/ragEvaluation'

function MetricCard({ row }) {
  return (
    <div className="rounded-md border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-gray-400">
          {row.short} / {row.label}
        </p>
        {row.invalid > 0 ? (
          <Badge variant="warning" size="sm">
            invalid {row.invalid}
          </Badge>
        ) : null}
      </div>
      <p className="mt-2 text-3xl font-bold text-gray-900">{formatScore(row.mean, 3)}</p>
      <p className="mt-1 text-xs text-gray-500">
        已评分 {row.evaluated} · 覆盖率 {formatPercent(row.coverage)}
        {row.skipped ? ` · 跳过 ${row.skipped}` : ''}
      </p>
      {row.mean === null ? (
        <p className="mt-1 text-[11px] text-gray-400">无有效评分（不伪装成 0）</p>
      ) : null}
    </div>
  )
}

export default function RagEvaluationDetail() {
  const { runId } = useParams()
  const runQuery = useRagEvaluationQuery(runId)
  const run = runQuery.data

  const resultsQuery = useRagEvaluationResultsQuery(runId, { limit: 100 })
  const failuresQuery = useRagEvaluationFailuresQuery(runId, { limit: 100 })
  const itemsQuery = useDatasetItemsQuery(run?.dataset_id, run?.dataset_version_id, {
    enabled: Boolean(run?.dataset_id && run?.dataset_version_id),
  })

  const itemMap = useMemo(() => {
    const map = new Map()
    for (const item of itemsQuery.data?.items || []) map.set(item.id, item)
    return map
  }, [itemsQuery.data])

  const cases = useMemo(
    () => groupResultsByItem(resultsQuery.data?.items || []),
    [resultsQuery.data]
  )
  const metricRows = judgeMetricRows(run?.aggregate)
  const issues = runKnownIssues(run)
  const failures = failuresQuery.data?.items || []
  const statusMeta = runStatusMeta(run?.status)

  if (runQuery.isLoading) return <PageLoading label="正在加载评测 Run..." />
  if (runQuery.isError) {
    return <AsyncState error={runQuery.error} onRetry={() => runQuery.refetch()} />
  }
  if (!run) {
    return (
      <Empty
        title="未找到评测 Run"
        description="该 Run 可能已被删除，或当前账号无权查看。"
        action={
          <Link to="/rag-evaluations" className="text-sm text-primary-600">
            返回 Run 列表
          </Link>
        }
      />
    )
  }

  const caseColumns = [
    {
      key: 'case',
      title: 'Case',
      dataIndex: 'itemId',
      render: (value, record) => {
        const item = itemMap.get(value)
        return (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-gray-900">{itemDisplayLabel(item)}</p>
            <p className="mt-0.5 truncate text-[11px] text-gray-500">
              {item?.query || `item ${shortId(value)}`}
            </p>
            <p className="mt-0.5 font-mono text-[10px] text-gray-400">
              {record.traceId ? `trace ${shortId(record.traceId)}` : 'no trace'}
            </p>
          </div>
        )
      },
    },
    ...['faithfulness', 'answer_correctness', 'answer_relevancy'].map(metric => ({
      key: metric,
      title: metricShort(metric),
      render: (_, record) => {
        const row = record.metrics[metric]
        if (!row) return <span className="text-xs text-gray-400">—</span>
        const meta = resultStatusMeta(row.status)
        return (
          <div className="space-y-1">
            <Badge variant={meta.variant} size="sm">
              {meta.label}
            </Badge>
            <p className="text-xs text-gray-700">{formatScore(row.score, 2)}</p>
          </div>
        )
      },
    })),
    {
      key: 'issue',
      title: 'invalid / 失败原因',
      render: (_, record) => {
        const issue = caseKnownIssue(record)
        if (!issue) return <span className="text-xs text-gray-400">—</span>
        return <span className="text-xs text-warning-700">{invalidReasonLabel(issue)}</span>
      },
    },
    {
      key: 'actions',
      title: '操作',
      render: (_, record) => (
        <Link
          to={`/rag-evaluations/${run.id}/cases/${record.itemId}`}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          查看 Case
        </Link>
      ),
    },
  ]

  const failureColumns = [
    {
      key: 'metric',
      title: '指标',
      dataIndex: 'metric_name',
      render: value => <span className="text-xs text-gray-700">{metricLabel(value)}</span>,
    },
    {
      key: 'status',
      title: '状态',
      dataIndex: 'status',
      render: value => {
        const meta = resultStatusMeta(value)
        return (
          <Badge variant={meta.variant} size="sm">
            {meta.label}
          </Badge>
        )
      },
    },
    {
      key: 'reason',
      title: '原因',
      render: (_, record) => (
        <span className="text-xs text-warning-700">
          {invalidReasonLabel(record.invalid_reason || record.error_message)}
        </span>
      ),
    },
    {
      key: 'case',
      title: '定位',
      render: (_, record) => (
        <Link
          to={`/rag-evaluations/${run.id}/cases/${record.dataset_item_id}`}
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
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">评测 Run 详情</h1>
              <Badge variant={statusMeta.variant}>{statusMeta.label}</Badge>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              {run.dataset_name} · {run.execution_mode} · {run.adapter} · 版本{' '}
              {shortId(run.dataset_version_id)} · 创建于 {formatDateTime(run.created_at)}
            </p>
            <p className="mt-0.5 font-mono text-[11px] text-gray-400">Run {run.id}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              icon={<LuRefreshCw className="h-4 w-4" />}
              onClick={() => {
                runQuery.refetch()
                resultsQuery.refetch()
                failuresQuery.refetch()
              }}
            >
              刷新
            </Button>
            <Link
              to="/reports"
              className="inline-flex h-10 items-center gap-2 rounded border border-gray-300 bg-white px-4 text-sm text-gray-700 transition-colors hover:bg-gray-50"
            >
              <LuFileText className="h-4 w-4" aria-hidden="true" />
              去报告中心
            </Link>
          </div>
        </div>
      </div>

      <RagBetaNotice issues={issues} />

      {run.error_message ? (
        <p
          role="alert"
          className="rounded border border-error-500/30 bg-error-50 p-3 text-sm text-error-700"
        >
          {run.error_message}
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {metricRows.map(row => (
          <MetricCard key={row.name} row={row} />
        ))}
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-gray-900">样本进度</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:grid-cols-7">
          {[
            ['总数', run.total_items],
            ['已评分', run.evaluated_items],
            ['invalid', run.invalid_items],
            ['失败', run.failed_items],
            ['跳过', run.skipped_items],
            ['未处理', run.unprocessed_items],
            ['完成任务', run.completed_items],
          ].map(([label, value]) => (
            <div key={label} className="rounded border border-gray-100 bg-gray-50 px-3 py-2">
              <p className="text-[11px] text-gray-500">{label}</p>
              <p className="text-lg font-semibold text-gray-900">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-gray-900">Known issues</h2>
        {issues.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">
            本 Run 没有 invalid / failed / skipped / unprocessed。
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {issues.map(issue => (
              <li key={issue.key} className="flex flex-col gap-1 text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="warning" size="sm">
                    {issue.label}
                  </Badge>
                  <span className="font-medium text-gray-900">{issue.count}</span>
                </div>
                <p className="text-xs text-gray-500">{issue.hint}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Case 列表</h2>
          <p className="text-xs text-gray-500">
            最多展示最近 100 条结果；F/C/R 逐条保留 status 与 invalid 原因。
          </p>
        </div>
        <AsyncState
          loading={resultsQuery.isLoading}
          error={resultsQuery.isError ? resultsQuery.error : null}
          onRetry={() => resultsQuery.refetch()}
        >
          {cases.length === 0 ? (
            <Empty
              title="还没有 Case 结果"
              description={
                run.status === 'running' || run.status === 'queued'
                  ? '评测仍在运行，稍后会逐步出现结果。'
                  : '本次 Run 没有产生可展示的结果。'
              }
            />
          ) : (
            <Table
              columns={caseColumns}
              dataSource={cases}
              rowKey="itemId"
              caption="RAG 评测 Case 列表"
            />
          )}
        </AsyncState>
      </div>

      <div>
        <h2 className="mb-2 text-lg font-semibold text-gray-900">失败与 invalid</h2>
        <AsyncState
          loading={failuresQuery.isLoading}
          error={failuresQuery.isError ? failuresQuery.error : null}
          onRetry={() => failuresQuery.refetch()}
        >
          {failures.length === 0 ? (
            <p className="rounded-md border border-dashed border-gray-300 bg-white p-6 text-sm text-gray-500">
              没有 failed 结果。
            </p>
          ) : (
            <Table
              columns={failureColumns}
              dataSource={failures}
              rowKey="id"
              caption="失败与 invalid 结果"
            />
          )}
        </AsyncState>
      </div>
    </section>
  )
}
