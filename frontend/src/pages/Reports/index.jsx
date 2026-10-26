import { useMemo, useState } from 'react'
import { LuFilePlus2, LuRefreshCw } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Pagination } from '../../components/Pagination'
import { Tabs } from '../../components/Tabs'
import { ReportPreview } from '../../components/business/ReportPreview'
import { CreateReportModal } from '../../components/reports/CreateReportModal'
import { ReportDetailModal } from '../../components/reports/ReportDetailModal'
import { useDeleteReport, useReportsQuery } from '../../hooks/useReports'
import { downloadReport } from '../../api/reports'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { downloadBlobFile } from '../../lib/download'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const PAGE_SIZE = 9

const FORMAT_EXTENSIONS = { markdown: 'md', excel: 'xlsx', pdf: 'pdf' }

const TYPE_TABS = [
  { key: 'all', label: '全部' },
  { key: 'quality', label: '质量分析' },
  { key: 'knowledge', label: '知识库' },
  { key: 'insight', label: '洞察' },
  { key: 'comprehensive', label: '综合分析' },
]

export default function Reports() {
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const [activeType, setActiveType] = useState('all')
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [detailReport, setDetailReport] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)

  const params = useMemo(
    () => ({
      page,
      limit: PAGE_SIZE,
      sort: '-created_at',
      ...(activeType === 'all' ? {} : { report_type: activeType }),
    }),
    [page, activeType]
  )

  const reportsQuery = useReportsQuery(currentDatasourceId, params)
  const deleteMutation = useDeleteReport()

  const reports = reportsQuery.data?.items || []
  const pagination = reportsQuery.data?.pagination

  const handleDownload = async report => {
    setDownloadingId(report.id)
    try {
      const blob = await downloadReport(report.id)
      const extension = FORMAT_EXTENSIONS[report.format] || 'md'
      downloadBlobFile(`report-${report.id}.${extension}`, blob)
    } catch (error) {
      notify.error(getErrorMessage(error))
    } finally {
      setDownloadingId(null)
    }
  }

  const handleDelete = async report => {
    try {
      await deleteMutation.mutateAsync(report.id)
      notify.success('报告已删除')
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">报告中心</h1>
          <p className="mt-1 text-sm text-gray-500">
            按需生成 4 类分析报告（markdown / excel / pdf），生成中每 3 秒刷新状态。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={<LuRefreshCw className="h-4 w-4" />}
            onClick={() => reportsQuery.refetch()}
            disabled={!currentDatasourceId}
          >
            刷新
          </Button>
          <Button
            icon={<LuFilePlus2 className="h-4 w-4" />}
            onClick={() => setCreateOpen(true)}
            disabled={!currentDatasourceId}
          >
            生成报告
          </Button>
        </div>
      </div>

      {!currentDatasourceId ? (
        <Empty
          title="尚未选择数据源"
          description="在顶部「数据源选择器」中选择数据源后生成/查看报告。"
        />
      ) : (
        <>
          <Tabs
            items={TYPE_TABS}
            value={activeType}
            onChange={value => {
              setActiveType(value)
              setPage(1)
            }}
          />

          {reportsQuery.isError ? (
            <AsyncState error={reportsQuery.error} onRetry={() => reportsQuery.refetch()} />
          ) : reportsQuery.isLoading ? (
            <PageLoading label="正在加载报告..." />
          ) : reports.length === 0 ? (
            <Empty
              title="暂无报告"
              description="点击「生成报告」选择报告类型与格式，生成完成后可预览/下载。"
            />
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {reports.map(report => (
                  <ReportPreview
                    key={report.id}
                    report={report}
                    downloading={downloadingId === report.id}
                    onPreview={item => setDetailReport(item)}
                    onDownload={handleDownload}
                    onDelete={handleDelete}
                  />
                ))}
              </div>

              {pagination && pagination.total > 0 ? (
                <Pagination
                  current={page}
                  pageSize={PAGE_SIZE}
                  total={pagination.total}
                  onChange={setPage}
                />
              ) : null}
            </>
          )}
        </>
      )}

      <CreateReportModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        datasourceId={currentDatasourceId}
      />
      <ReportDetailModal
        open={Boolean(detailReport)}
        onClose={() => setDetailReport(null)}
        report={detailReport}
      />
    </section>
  )
}
