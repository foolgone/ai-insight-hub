import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { LuPlus, LuRefreshCw } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Pagination } from '../../components/Pagination'
import { Progress } from '../../components/Progress'
import { Table } from '../../components/Table'
import { CreateEvaluationModal } from '../../components/quality/CreateEvaluationModal'
import { useQualityResultsQuery } from '../../hooks/useQuality'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { formatDateTime } from '../../lib/format'
import { countQualityLevels, qualityLevelForScore, QUALITY_LEVELS } from '../../lib/quality'

const PAGE_SIZE = 10

function OverviewCards({ distribution }) {
  const total = distribution.reduce((sum, item) => sum + item.value, 0)
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {QUALITY_LEVELS.map(level => {
        const entry = distribution.find(item => item.key === level.key)
        const value = entry?.value ?? 0
        const percent = total > 0 ? Math.round((value / total) * 100) : 0
        return (
          <div key={level.key} className="rounded-md border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">{level.label}</span>
              <Badge variant={level.variant} size="sm">
                {value}
              </Badge>
            </div>
            <p className="mt-2 text-2xl font-bold text-gray-900">{percent}%</p>
            <Progress percent={percent} className="mt-2" />
          </div>
        )
      })}
    </div>
  )
}

export default function QualityAssessment() {
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)

  const listQuery = useQualityResultsQuery(currentDatasourceId, {
    page,
    limit: PAGE_SIZE,
    sort: '-created_at',
  })
  const overviewQuery = useQualityResultsQuery(currentDatasourceId, {
    page: 1,
    limit: 100,
    sort: '-created_at',
  })

  const items = useMemo(() => listQuery.data?.items || [], [listQuery.data])
  const distribution = useMemo(
    () => countQualityLevels(overviewQuery.data?.items || []),
    [overviewQuery.data]
  )
  const summary = listQuery.data?.summary
  const pagination = listQuery.data?.pagination

  const columns = [
    {
      key: 'score',
      title: '总分',
      dataIndex: 'overall_score',
      render: value => {
        const level = qualityLevelForScore(value)
        return (
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-gray-900">{Math.round(value)}</span>
            <Badge variant={level.variant} size="sm">
              {level.label}
            </Badge>
          </div>
        )
      },
    },
    {
      key: 'needs_review',
      title: '复核状态',
      dataIndex: 'needs_review',
      render: value =>
        value ? (
          <Badge variant="warning" size="sm">
            待复核
          </Badge>
        ) : (
          <Badge variant="success" size="sm">
            无需复核
          </Badge>
        ),
    },
    {
      key: 'agent',
      title: 'Agent 版本',
      dataIndex: 'agent_version',
      render: value => value || '—',
    },
    {
      key: 'created_at',
      title: '创建时间',
      dataIndex: 'created_at',
      render: value => formatDateTime(value),
    },
    {
      key: 'actions',
      title: '操作',
      render: (_, item) => (
        <Link
          to={`/quality-assessment/${item.id}`}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          查看详情
        </Link>
      ),
    },
  ]

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">质量评估</h1>
          <p className="mt-1 text-sm text-gray-500">
            5 维质量评估（0–100），等级按分数计算；4 档分布取最近 100 条样本。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={<LuRefreshCw className="h-4 w-4" />}
            onClick={() => {
              listQuery.refetch()
              overviewQuery.refetch()
            }}
          >
            刷新
          </Button>
          <Button
            icon={<LuPlus className="h-4 w-4" />}
            onClick={() => setCreateOpen(true)}
            disabled={!currentDatasourceId}
          >
            新建评估任务
          </Button>
        </div>
      </div>

      {!currentDatasourceId ? (
        <Empty
          title="尚未选择数据源"
          description="在顶部「数据源选择器」中选择数据源后查看评估结果。"
        />
      ) : listQuery.isError ? (
        <AsyncState error={listQuery.error} onRetry={() => listQuery.refetch()} />
      ) : listQuery.isLoading ? (
        <PageLoading label="正在加载评估结果..." />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
            <span>
              平均分：
              <span className="font-semibold text-gray-900">
                {Number(summary?.avg_overall_score ?? 0).toFixed(1)}
              </span>
            </span>
            <span>
              待复核：
              <span className="font-semibold text-gray-900">
                {summary?.needs_review_count ?? 0}
              </span>
            </span>
            <span>
              样本总数：<span className="font-semibold text-gray-900">{summary?.total ?? 0}</span>
            </span>
          </div>

          <OverviewCards distribution={distribution} />

          <div className="rounded-md border border-gray-200 bg-white p-4">
            <h2 className="mb-3 text-lg font-semibold text-gray-900">评估结果</h2>
            <Table
              columns={columns}
              dataSource={items}
              loading={listQuery.isLoading}
              emptyText="暂无评估结果，先新建评估任务"
              caption="质量评估结果列表"
            />
            {pagination && pagination.total > 0 ? (
              <Pagination
                current={page}
                pageSize={PAGE_SIZE}
                total={pagination.total}
                onChange={setPage}
                className="mt-3"
              />
            ) : null}
          </div>
        </>
      )}

      <CreateEvaluationModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        datasourceId={currentDatasourceId}
      />
    </section>
  )
}
