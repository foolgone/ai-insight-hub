import clsx from 'clsx'

const COLORS = {
  primary: 'bg-primary-50 text-primary-600',
  success: 'bg-success-50 text-success-600',
  warning: 'bg-warning-50 text-warning-600',
  error: 'bg-error-50 text-error-600',
}

/**
 * 统计卡片（02 §3.3）：图标 + 数值 + 趋势。
 * @param {{
 *   title: string,
 *   value: string|number,
 *   icon: React.ReactNode,
 *   trend?: { value: number, direction: 'up'|'down' },
 *   color?: 'primary'|'success'|'warning'|'error',
 *   className?: string,
 * }} props
 */
export function StatCard({ title, value, icon, trend, color = 'primary', className }) {
  return (
    <div
      className={clsx(
        'flex items-start justify-between gap-3 rounded-md border border-gray-200 bg-white p-5',
        className
      )}
    >
      <div className="min-w-0">
        <p className="text-sm text-gray-600">{title}</p>
        <p className="mt-1 text-3xl font-bold text-gray-900">{value}</p>
        {trend ? (
          <p
            className={clsx(
              'mt-1 text-xs font-medium',
              trend.direction === 'up' ? 'text-success-600' : 'text-error-600'
            )}
          >
            <span aria-hidden="true">{trend.direction === 'up' ? '↑' : '↓'}</span>{' '}
            {Math.abs(trend.value)}%
          </p>
        ) : null}
      </div>
      <div
        className={clsx(
          'grid h-10 w-10 shrink-0 place-items-center rounded-md',
          COLORS[color] || COLORS.primary
        )}
        aria-hidden="true"
      >
        {icon}
      </div>
    </div>
  )
}
