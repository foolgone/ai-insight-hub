import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { LuArrowLeftRight, LuPlus, LuRefreshCw } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageHeader } from '../../components/common/PageHeader'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Pagination } from '../../components/Pagination'
import { Select } from '../../components/Select'
import { Table } from '../../components/Table'
import { CreateRagEvaluationModal } from '../../components/rag/CreateRagEvaluationModal'
import { RagBetaNotice } from '../../components/rag/RagBetaNotice'
import { useRagEvaluationsQuery } from '../../hooks/useRagEvaluations'
import { formatDateTime } from '../../lib/format'
import { formatScore, judgeMetricRows, runStatusMeta, shortId } from '../../lib/ragEvaluation'

const PAGE_SIZE = 10

const STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: '排队中', value: 'queued' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
]

export default function RagEvaluations() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [notice, setNotice] = useState('')

  const params = useMemo(
    () => ({ page, limit: PAGE_SIZE, ...(status ? { status } : {}) }),
    [page, status]
  )
  const query = useRagEvaluationsQuery(params)
  const items = query.data?.items || []
  const pagination = query.data?.pagination

  const columns = [
    {
      key: 'status',
      title: '状态',
      dataIndex: 'status',
      render: value => {
        const meta = runStatusMeta(value)
        return (
          <div className="flex flex-col gap-1">
            <Badge variant={meta.variant} size="sm">
              {meta.label}
            </Badge>
            <span className="text-[11px] text-gray-400">{value}</span>
          </div>
        )
      },
    },
    {
      key: 'dataset',
      title: '数据集 / 模式',
      dataIndex: 'dataset_name',
      render: (value, record) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900">{value || '—'}</p>
          <p className="mt-0.5 text-[11px] text-gray-500">
            {record.execution_mode} · {record.adapter} · 版本 {shortId(record.dataset_version_id)}
          </p>
        </div>
      ),
    },
    {
      key: 'items',
      title: '样本',
      dataIndex: 'total_items',
      render: (value, record) => (
        <div className="space-y-1 text-xs">
          <p className="text-gray-700">
            已评分 <span className="font-medium">{record.evaluated_items}</span> /{' '}
            {record.total_items}
          </p>
          <div className="flex flex-wrap gap-1">
            {record.invalid_items > 0 ? (
              <Badge variant="warning" size="sm">
                invalid {record.invalid_items}
              </Badge>
            ) : null}
            {record.failed_items > 0 ? (
              <Badge variant="error" size="sm">
                failed {record.failed_items}
              </Badge>
            ) : null}
            {record.invalid_items === 0 && record.failed_items === 0 ? (
              <span className="text-[11px] text-gray-400">无 invalid / failed</span>
            ) : null}
          </div>
        </div>
      ),
    },
    {
      key: 'metrics',
      title: 'F / C / R',
      render: (_, record) => {
        const rows = judgeMetricRows(record.aggregate)
        return (
          <div className="flex gap-3 text-xs">
            {rows.map(row => (
              <div key={row.name}>
                <p className="font-mono text-[10px] uppercase tracking-wide text-gray-400">
                  {row.short}
                </p>
                <p className="font-medium text-gray-900">{formatScore(row.mean, 2)}</p>
              </div>
            ))}
          </div>
        )
      },
    },
    {
      key: 'time',
      title: '时间',
      dataIndex: 'created_at',
      render: (value, record) => (
        <div className="text-xs text-gray-600">
          <p>创建 {formatDateTime(value)}</p>
          <p className="text-[11px] text-gray-400">
            {record.completed_at ? `完成 ${formatDateTime(record.completed_at)}` : '—'}
          </p>
        </div>
      ),
    },
    {
      key: 'actions',
      title: '操作',
      render: (_, record) => (
        <Link
          to={`/rag-evaluations/${record.id}`}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          查看详情
        </Link>
      ),
    },
  ]

  return (
    <section className="space-y-6">
      <PageHeader
        index="05"
        eyebrow="RAG Evaluation"
        title="RAG 评测"
        description="Run 列表、指标汇总与 invalid / known issues。Judge 为 beta，结果需人工复核。"
        actions={
          <>
            <Button
              variant="outline"
              icon={<LuRefreshCw className="h-4 w-4" />}
              onClick={() => query.refetch()}
            >
              刷新
            </Button>
            <Link
              to="/rag-evaluations/compare"
              className="inline-flex h-10 items-center gap-2 rounded border border-gray-300 bg-white px-4 text-sm text-gray-700 transition-colors hover:bg-gray-50"
            >
              <LuArrowLeftRight className="h-4 w-4" aria-hidden="true" />
              对比 Run
            </Link>
            <Button icon={<LuPlus className="h-4 w-4" />} onClick={() => setCreateOpen(true)}>
              新建评测
            </Button>
          </>
        }
      />

      <RagBetaNotice />

      {notice ? (
        <p
          role="status"
          className="rounded border border-success-500/30 bg-success-50 p-3 text-sm text-success-700"
        >
          {notice}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <div className="w-44">
          <Select
            options={STATUS_OPTIONS}
            value={status}
            onChange={value => {
              setStatus(value)
              setPage(1)
            }}
            ariaLabel="按状态筛选"
          />
        </div>
        <p className="text-xs text-gray-500">
          共 {pagination?.total ?? 0} 个 Run；运行中的 Run 每 5s 自动刷新。
        </p>
      </div>

      <AsyncState
        loading={query.isLoading}
        error={query.isError ? query.error : null}
        onRetry={() => query.refetch()}
      >
        {items.length === 0 ? (
          <Empty
            title="还没有 RAG 评测 Run"
            description="创建一次评测后，这里会显示状态、指标和 invalid 计数。"
          />
        ) : (
          <Table columns={columns} dataSource={items} rowKey="id" caption="RAG 评测 Run 列表" />
        )}
      </AsyncState>

      {pagination && pagination.total > PAGE_SIZE ? (
        <Pagination
          current={pagination.page}
          pageSize={pagination.limit}
          total={pagination.total}
          onChange={nextPage => setPage(nextPage)}
        />
      ) : null}

      <CreateRagEvaluationModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={created => {
          setNotice(`已创建 Run ${shortId(created?.run_id)}，任务已入队。`)
          setPage(1)
          query.refetch()
        }}
      />
    </section>
  )
}
