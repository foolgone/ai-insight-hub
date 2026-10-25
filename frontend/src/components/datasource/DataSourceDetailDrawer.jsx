import * as Dialog from '@radix-ui/react-dialog'
import { LuCheckCircle2, LuClock, LuX } from 'react-icons/lu'
import { Badge } from '../Badge'
import { getDatasourceStatus, getDatasourceTypeLabel } from '../../lib/datasourceMeta'
import { formatDateTime, formatNumber } from '../../lib/format'

/**
 * 数据源详情抽屉（F-205）：展示配置/统计/派生进度，不依赖 workflow_status（D-F22）。
 * @param {{ datasource: Object|null, open: boolean, onClose: () => void }} props
 */
export function DataSourceDetailDrawer({ datasource, open, onClose }) {
  if (!datasource) return null

  const status = getDatasourceStatus(datasource.status)
  const statistics = datasource.statistics || {}
  const config = datasource.config || {}

  const steps = [
    { key: 'uploaded', label: '已上传', done: Number(statistics.total_records || 0) > 0 },
    { key: 'cleaned', label: '已清洗', done: Number(statistics.cleaned_records || 0) > 0 },
    { key: 'evaluated', label: '已评估', done: Number(statistics.quality_score_avg || 0) > 0 },
  ]

  return (
    <Dialog.Root open={open} onOpenChange={nextOpen => (nextOpen ? undefined : onClose())}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[480px] flex-col bg-white shadow-xl focus:outline-none"
        >
          <header className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-4">
            <Dialog.Title className="text-lg font-semibold text-gray-900">数据源详情</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="关闭"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-gray-500 hover:bg-gray-100"
              >
                <LuX className="h-4 w-4" aria-hidden="true" />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="truncate text-lg font-semibold text-gray-900">{datasource.name}</h3>
                <Badge variant={status.variant} size="sm">
                  {status.label}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-gray-500">
                {getDatasourceTypeLabel(datasource.type)} · 创建于{' '}
                {formatDateTime(datasource.created_at)}
              </p>
              {datasource.description ? (
                <p className="mt-2 text-sm text-gray-600">{datasource.description}</p>
              ) : null}
            </div>

            <section aria-label="处理进度">
              <h4 className="text-sm font-semibold text-gray-900">处理进度</h4>
              <ol className="mt-3 flex flex-wrap gap-4">
                {steps.map(step => (
                  <li
                    key={step.key}
                    className={
                      step.done
                        ? 'flex items-center gap-1.5 text-sm text-success-700'
                        : 'flex items-center gap-1.5 text-sm text-gray-400'
                    }
                  >
                    {step.done ? (
                      <LuCheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <LuClock className="h-4 w-4" aria-hidden="true" />
                    )}
                    {step.label}
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-gray-500">
                按统计数据派生，上传/清洗/评估完成后自动更新。
              </p>
            </section>

            <section aria-label="统计信息">
              <h4 className="text-sm font-semibold text-gray-900">统计信息</h4>
              <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-gray-500">数据量</dt>
                  <dd className="text-gray-900">{formatNumber(statistics.total_records)} 条</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">已清洗</dt>
                  <dd className="text-gray-900">{formatNumber(statistics.cleaned_records)} 条</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">质量均分</dt>
                  <dd className="text-gray-900">
                    {Number(statistics.quality_score_avg || 0).toFixed(1)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">最后处理</dt>
                  <dd className="text-gray-900">{formatDateTime(statistics.last_processed_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">更新时间</dt>
                  <dd className="text-gray-900">{formatDateTime(datasource.updated_at)}</dd>
                </div>
              </dl>
            </section>

            <section aria-label="配置">
              <h4 className="text-sm font-semibold text-gray-900">配置</h4>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-gray-500">自动清洗</dt>
                  <dd className="text-gray-900">{config.auto_clean ? '开启' : '关闭'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-gray-500">自动评估</dt>
                  <dd className="text-gray-900">{config.auto_evaluate ? '开启' : '关闭'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-gray-500">评估维度</dt>
                  <dd className="text-right text-gray-900">
                    {Array.isArray(config.evaluation_dimensions) &&
                    config.evaluation_dimensions.length > 0
                      ? config.evaluation_dimensions.join('、')
                      : '默认 5 维'}
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
