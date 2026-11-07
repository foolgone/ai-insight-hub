import clsx from 'clsx'

const DOT_COLORS = {
  primary: 'bg-primary-500',
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  error: 'bg-error-500',
  info: 'bg-info-500',
}

/**
 * 统计卡片（编辑部风格）：细线顶栏 + 衬线大数字，不使用图标色块。
 * @param {{
 *   title: string,
 *   value: string|number,
 *   icon?: React.ReactNode,
 *   trend?: { value: number, direction: 'up'|'down' },
 *   color?: 'primary'|'success'|'warning'|'error'|'info',
 *   className?: string,
 * }} props
 */
export function StatCard({ title, value, icon, trend, color = 'primary', className }) {
  return (
    <div className={clsx('group relative border-t border-gray-300 pt-4', className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-gray-500">
          <span
            className={clsx('h-1.5 w-1.5 rounded-full', DOT_COLORS[color] || DOT_COLORS.primary)}
            aria-hidden="true"
          />
          {title}
        </p>
        {icon ? (
          <span className="text-gray-300 transition-colors group-hover:text-gray-500" aria-hidden="true">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="mt-4 font-display text-4xl font-normal leading-none tracking-tight text-gray-900 num">
        {value}
      </p>
      {trend ? (
        <p
          className={clsx(
            'mt-3 font-mono text-[11px] tracking-wide',
            trend.direction === 'up' ? 'text-success-600' : 'text-error-600'
          )}
        >
          <span aria-hidden="true">{trend.direction === 'up' ? '↑' : '↓'}</span>{' '}
          {Math.abs(trend.value)}%
        </p>
      ) : null}
    </div>
  )
}
