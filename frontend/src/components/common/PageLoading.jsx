/**
 * 页面级加载态（F-105）。
 * @param {{ label?: string }} props
 */
export function PageLoading({ label = '加载中...' }) {
  return (
    <div
      role="status"
      className="flex min-h-[200px] flex-col items-center justify-center gap-3 text-sm text-gray-500"
    >
      <span
        className="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"
        aria-hidden="true"
      />
      {label}
    </div>
  )
}
