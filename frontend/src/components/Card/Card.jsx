import clsx from 'clsx'

/**
 * 卡片（02 §3.2）。
 * @param {{
 *   title?: React.ReactNode,
 *   extra?: React.ReactNode,
 *   footer?: React.ReactNode,
 *   hoverable?: boolean,
 *   variant?: 'default'|'flat'|'hoverable',
 *   bordered?: boolean,
 *   loading?: boolean,
 *   className?: string,
 *   children?: React.ReactNode,
 * }} props
 */
export function Card({
  title,
  extra,
  footer,
  hoverable = false,
  variant = 'default',
  bordered = true,
  loading = false,
  className,
  children,
}) {
  return (
    <section
      aria-busy={loading || undefined}
      className={clsx(
        'rounded-md bg-white transition-shadow',
        bordered && 'border border-gray-200',
        variant === 'flat'
          ? 'shadow-none'
          : variant === 'hoverable' || hoverable
            ? 'hover:shadow-md'
            : 'shadow',
        className
      )}
    >
      {title || extra ? (
        <header className="flex items-center justify-between gap-3 border-b border-gray-100 px-6 py-4">
          {title ? <h2 className="text-lg font-semibold text-gray-900">{title}</h2> : null}
          {extra ? <div className="shrink-0">{extra}</div> : null}
        </header>
      ) : null}

      <div className="p-6">
        {loading ? (
          <div className="space-y-3" role="status" aria-label="加载中">
            {[0, 1, 2].map(index => (
              <div key={index} className="h-4 animate-pulse rounded bg-gray-200" />
            ))}
          </div>
        ) : (
          children
        )}
      </div>

      {footer ? (
        <footer className="border-t border-gray-100 px-6 py-4 text-sm text-gray-600">
          {footer}
        </footer>
      ) : null}
    </section>
  )
}
