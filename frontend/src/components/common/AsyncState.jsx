import { Button } from '../Button'
import { getErrorMessage } from '../../lib/errorMessages'
import { PageLoading } from './PageLoading'

/**
 * 列表/详情通用异步状态：loading / error / empty / 内容（F-105）。
 * @param {{
 *   loading?: boolean,
 *   error?: any,
 *   isEmpty?: boolean,
 *   emptyText?: string,
 *   loadingFallback?: React.ReactNode,
 *   onRetry?: () => void,
 *   children?: React.ReactNode,
 * }} props
 */
export function AsyncState({
  loading = false,
  error = null,
  isEmpty = false,
  emptyText = '暂无数据',
  loadingFallback,
  onRetry,
  children,
}) {
  if (loading) return loadingFallback || <PageLoading />

  if (error) {
    return (
      <div
        role="alert"
        className="flex flex-col items-center gap-3 rounded-md border border-error-200 bg-error-50 p-6 text-center text-sm text-error-700"
      >
        <p>{getErrorMessage(error)}</p>
        {onRetry ? (
          <Button size="sm" variant="outline" onClick={onRetry}>
            重试
          </Button>
        ) : null}
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div className="rounded-md border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
        {emptyText}
      </div>
    )
  }

  return children
}
