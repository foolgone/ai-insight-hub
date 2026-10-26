import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { Spinner } from '../Spinner'
import { Markdown } from '../common/Markdown'
import { useReportQuery } from '../../hooks/useReports'
import { downloadReport } from '../../api/reports'
import { downloadBlobFile } from '../../lib/download'
import { formatDateTime } from '../../lib/format'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const TYPE_LABELS = {
  quality: '质量分析报告',
  knowledge: '知识库报告',
  insight: '洞察报告',
  comprehensive: '综合分析报告',
}

const FORMAT_EXTENSIONS = { markdown: 'md', excel: 'xlsx', pdf: 'pdf' }

/**
 * 报告详情/预览（F-408）：markdown 显示渲染内容；excel/pdf 仅下载。
 * @param {{ open: boolean, onClose: () => void, report: Object|null }} props
 */
export function ReportDetailModal({ open, onClose, report }) {
  const detailQuery = useReportQuery(open ? report?.id : null)
  const detail = detailQuery.data
  const [markdown, setMarkdown] = useState('')
  const [contentError, setContentError] = useState('')

  useEffect(() => {
    if (!open) {
      setMarkdown('')
      setContentError('')
      return
    }
    if (!detail || detail.status !== 'completed' || detail.format !== 'markdown') return

    let cancelled = false
    setMarkdown('')
    setContentError('')
    downloadReport(detail.id)
      .then(blob => (typeof blob.text === 'function' ? blob.text() : ''))
      .then(text => {
        if (!cancelled) setMarkdown(text)
      })
      .catch(error => {
        if (!cancelled) setContentError(getErrorMessage(error))
      })

    return () => {
      cancelled = true
    }
  }, [open, detail])

  const handleDownload = async () => {
    if (!detail) return
    try {
      const blob = await downloadReport(detail.id)
      const extension = FORMAT_EXTENSIONS[detail.format] || 'md'
      downloadBlobFile(`report-${detail.id}.${extension}`, blob)
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={detail?.title || report?.title || '报告详情'}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            关闭
          </Button>
          {detail?.status === 'completed' ? <Button onClick={handleDownload}>下载</Button> : null}
        </>
      }
    >
      {detailQuery.isLoading ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : detailQuery.isError ? (
        <p role="alert" className="text-sm text-error-700">
          {getErrorMessage(detailQuery.error)}
        </p>
      ) : detail ? (
        <div className="space-y-4">
          <dl className="grid gap-2 text-xs text-gray-500 sm:grid-cols-2">
            <div>
              类型：
              <span className="text-gray-700">
                {TYPE_LABELS[detail.report_type] || detail.report_type}
              </span>
            </div>
            <div>
              格式：<span className="text-gray-700">{String(detail.format).toUpperCase()}</span>
            </div>
            <div>
              创建：
              <span className="text-gray-700">{formatDateTime(detail.created_at)}</span>
            </div>
            <div>
              完成：
              <span className="text-gray-700">{formatDateTime(detail.completed_at)}</span>
            </div>
          </dl>

          {detail.status !== 'completed' ? (
            <p className="rounded bg-gray-50 p-3 text-sm text-gray-600">
              报告{detail.status === 'failed' ? '生成失败' : '生成中'}，完成后可预览/下载。
              {detail.error_message ? `（${detail.error_message}）` : ''}
            </p>
          ) : detail.format === 'markdown' ? (
            contentError ? (
              <p role="alert" className="text-sm text-error-700">
                {contentError}
              </p>
            ) : markdown ? (
              <div className="max-h-[60vh] overflow-y-auto rounded border border-gray-200 p-4">
                <Markdown>{markdown}</Markdown>
              </div>
            ) : (
              <div className="flex justify-center py-8">
                <Spinner label="正在加载报告内容..." />
              </div>
            )
          ) : (
            <p className="rounded bg-gray-50 p-3 text-sm text-gray-600">
              {detail.format === 'pdf' ? 'PDF' : 'Excel'} 报告不提供在线预览，请点击「下载」查看。
            </p>
          )}
        </div>
      ) : null}
    </Modal>
  )
}
