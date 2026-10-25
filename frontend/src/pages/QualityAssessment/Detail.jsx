import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LuArrowLeft } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Chart } from '../../components/Chart'
import { Empty } from '../../components/Empty'
import { QualityScoreDisplay } from '../../components/business/QualityScoreDisplay'
import { ReviewModal } from '../../components/quality/ReviewModal'
import { useCleanedDataDetailQuery } from '../../hooks/useCleaning'
import { useQualityResultsQuery } from '../../hooks/useQuality'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { EVALUATION_DIMENSIONS, dimensionLabel } from '../../lib/evaluation'
import { formatDateTime } from '../../lib/format'
import { qualityLevelForScore } from '../../lib/quality'

export default function QualityAssessmentDetail() {
  const { id } = useParams()
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const [reviewOpen, setReviewOpen] = useState(false)

  const listQuery = useQualityResultsQuery(
    currentDatasourceId,
    { page: 1, limit: 100, sort: '-created_at' },
    { enabled: Boolean(currentDatasourceId) }
  )

  const result = useMemo(
    () => (listQuery.data?.items || []).find(item => String(item.id) === String(id)),
    [listQuery.data, id]
  )

  const cleanedQuery = useCleanedDataDetailQuery(currentDatasourceId, result?.data_id)

  const dimensionChartData = useMemo(() => {
    if (!result?.dimensions) return []
    return EVALUATION_DIMENSIONS.map(item => ({
      name: dimensionLabel(item.key),
      value: Number(result.dimensions?.[item.key]?.score ?? 0),
    }))
  }, [result])

  const issues = useMemo(() => {
    if (!result?.dimensions) return []
    return Object.entries(result.dimensions).flatMap(([key, value]) => {
      const list = Array.isArray(value?.issues) ? value.issues : []
      return list.map(issue => ({ key: `${key}-${issue}`, dimension: dimensionLabel(key), issue }))
    })
  }, [result])

  const renderShell = content => (
    <section className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">评估详情</h1>
      {content}
    </section>
  )

  if (!currentDatasourceId) {
    return renderShell(
      <Empty
        title="尚未选择数据源"
        description="在顶部「数据源选择器」中选择数据源后查看评估详情。"
      />
    )
  }

  if (listQuery.isLoading) return renderShell(<PageLoading label="正在加载评估结果..." />)
  if (listQuery.isError) {
    return renderShell(<AsyncState error={listQuery.error} onRetry={() => listQuery.refetch()} />)
  }

  if (!result) {
    return renderShell(
      <Empty
        title="未找到评估结果"
        description="该结果可能已被清理，或不在最近 100 条评估记录中。"
        action={
          <Link
            to="/quality-assessment"
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            返回评估列表
          </Link>
        }
      />
    )
  }

  const level = qualityLevelForScore(result.overall_score)
  const cleaned = cleanedQuery.data

  return (
    <section className="space-y-6">
      <div>
        <Link
          to="/quality-assessment"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <LuArrowLeft className="h-4 w-4" aria-hidden="true" />
          返回评估列表
        </Link>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">评估详情</h1>
            <p className="mt-1 text-xs text-gray-500">
              评估 ID：{result.id} · 创建于 {formatDateTime(result.created_at)}
              {result.agent_version ? ` · ${result.agent_version}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={result.needs_review ? 'warning' : 'success'}>
              {result.needs_review ? '待人工复核' : '无需复核'}
            </Badge>
            {result.needs_review ? (
              <Button onClick={() => setReviewOpen(true)}>人工复核</Button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-gray-200 bg-white p-6">
          <QualityScoreDisplay score={result.overall_score} size="lg" />
          <p className="text-sm text-gray-500">总分（0–100）</p>
          <p className="text-xs text-gray-400">等级按总分计算（{level.label}）</p>
        </div>
        <div className="rounded-md border border-gray-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 text-lg font-semibold text-gray-900">各维度得分</h2>
          <Chart
            title="5 维得分"
            type="bar"
            data={dimensionChartData}
            height={260}
            showToolbar={false}
          />
        </div>
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-lg font-semibold text-gray-900">维度问题</h2>
        {issues.length === 0 ? (
          <p className="text-sm text-gray-500">各维度均未标记问题。</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {issues.map(item => (
              <li key={item.key} className="flex flex-wrap items-center gap-2">
                <Badge variant="warning" size="sm">
                  {item.dimension}
                </Badge>
                <span className="text-gray-700">{item.issue}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-gray-500">
          改进建议（suggestions）当前评估接口不返回，MVP 不展示。
        </p>
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-lg font-semibold text-gray-900">对话原文</h2>
        {cleanedQuery.isLoading ? (
          <PageLoading label="正在加载对话..." />
        ) : cleanedQuery.isError ? (
          <AsyncState error={cleanedQuery.error} onRetry={() => cleanedQuery.refetch()} />
        ) : cleaned ? (
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-xs text-gray-500">用户消息</p>
              <p className="mt-1 whitespace-pre-wrap rounded bg-gray-50 p-3 text-gray-700">
                {cleaned.user_message}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">AI 回复</p>
              <p className="mt-1 whitespace-pre-wrap rounded bg-gray-50 p-3 text-gray-700">
                {cleaned.ai_response}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">暂无对话原文（cleaned-data 详情不可用）。</p>
        )}
      </div>

      <ReviewModal
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        datasourceId={currentDatasourceId}
        result={result}
      />
    </section>
  )
}
