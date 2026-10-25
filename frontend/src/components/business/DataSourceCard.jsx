import clsx from 'clsx'
import { Badge } from '../Badge'
import { getDatasourceStatus, getDatasourceTypeLabel } from '../../lib/datasourceMeta'
import { formatDateTime } from '../../lib/format'

/**
 * 数据源卡片（02 §6.1 / 03 §3.3）。
 * @param {{ datasource: Object, actions?: React.ReactNode }} props
 */
export function DataSourceCard({ datasource, actions }) {
  const status = getDatasourceStatus(datasource.status)
  const statistics = datasource.statistics || {}
  const typeLabel = getDatasourceTypeLabel(datasource.type)

  return (
    <article className="flex flex-col gap-3 border-b border-gray-200 px-6 py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={clsx('h-2 w-2 shrink-0 rounded-full', {
              'bg-success-500': datasource.status === 'active',
              'bg-warning-500': datasource.status === 'processing',
              'bg-gray-400': datasource.status === 'archived',
              'bg-error-500': datasource.status === 'error',
            })}
            aria-hidden="true"
          />
          <h3 className="truncate text-lg font-semibold text-gray-900">{datasource.name}</h3>
          <Badge variant={status.variant} size="sm">
            {status.label}
          </Badge>
        </div>

        <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
          <div className="flex gap-1">
            <dt>类型：</dt>
            <dd className="text-gray-700">{typeLabel}</dd>
          </div>
          <div className="flex gap-1">
            <dt>数据量：</dt>
            <dd className="text-gray-700">{statistics.total_records ?? 0} 条</dd>
          </div>
          <div className="flex gap-1">
            <dt>已清洗：</dt>
            <dd className="text-gray-700">{statistics.cleaned_records ?? 0} 条</dd>
          </div>
          <div className="flex gap-1">
            <dt>质量均分：</dt>
            <dd className="text-gray-700">
              {Number(statistics.quality_score_avg || 0).toFixed(1)}
            </dd>
          </div>
          <div className="flex gap-1">
            <dt>最后处理：</dt>
            <dd className="text-gray-700">{formatDateTime(statistics.last_processed_at)}</dd>
          </div>
        </dl>
      </div>

      {actions ? <div className="shrink-0">{actions}</div> : null}
    </article>
  )
}
