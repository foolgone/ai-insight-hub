import { LuFileText } from 'react-icons/lu'
import { Badge } from '../Badge'
import { Button } from '../Button'
import { Popconfirm } from '../Popconfirm'
import { formatDateTime } from '../../lib/format'

const TYPE_META = {
  quality: { label: '质量分析', variant: 'primary' },
  knowledge: { label: '知识库', variant: 'success' },
  insight: { label: '洞察', variant: 'warning' },
  comprehensive: { label: '综合分析', variant: 'info' },
}

const STATUS_META = {
  pending: { label: '排队中', variant: 'default' },
  running: { label: '生成中', variant: 'info' },
  generating: { label: '生成中', variant: 'info' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失败', variant: 'error' },
}

function formatFileSize(size) {
  if (!size && size !== 0) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * 报告卡片（02 §6.5 / 03 §3.7）。
 * @param {{
 *   report: Object,
 *   onPreview?: (report: Object) => void,
 *   onDownload?: (report: Object) => void,
 *   onDelete?: (report: Object) => void,
 *   downloading?: boolean,
 * }} props
 */
export function ReportPreview({ report, onPreview, onDownload, onDelete, downloading = false }) {
  const type = TYPE_META[report.report_type] || { label: report.report_type, variant: 'default' }
  const status = STATUS_META[report.status] || { label: report.status, variant: 'default' }
  const completed = report.status === 'completed'

  return (
    <article className="flex h-full flex-col rounded-md border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded bg-primary-50 text-primary-600">
            <LuFileText className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-gray-900" title={report.title}>
              {report.title}
            </h3>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Badge variant={type.variant} size="sm">
                {type.label}
              </Badge>
              <Badge variant="default" size="sm">
                {String(report.format || '').toUpperCase()}
              </Badge>
              <Badge variant={status.variant} size="sm">
                {status.label}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <dl className="mt-3 flex-1 space-y-1 text-xs text-gray-500">
        <div className="flex gap-1">
          <dt>创建：</dt>
          <dd className="text-gray-700">{formatDateTime(report.created_at)}</dd>
        </div>
        <div className="flex gap-1">
          <dt>大小：</dt>
          <dd className="text-gray-700">{formatFileSize(report.file_size)}</dd>
        </div>
      </dl>

      <div className="mt-3 flex items-center justify-end gap-1 border-t border-gray-100 pt-3">
        {completed && onPreview ? (
          <Button size="sm" variant="ghost" onClick={() => onPreview(report)}>
            预览
          </Button>
        ) : null}
        {completed && onDownload ? (
          <Button
            size="sm"
            variant="outline"
            loading={downloading}
            onClick={() => onDownload(report)}
          >
            下载
          </Button>
        ) : null}
        {onDelete ? (
          <Popconfirm
            title="删除该报告？"
            description="删除后不可恢复。"
            onConfirm={() => onDelete(report)}
          >
            <Button size="sm" variant="ghost">
              删除
            </Button>
          </Popconfirm>
        ) : null}
      </div>
    </article>
  )
}
