import clsx from 'clsx'

/**
 * 卡片（编辑部风格）：细线边框、无阴影、衬线小标题。
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
        'bg-white transition-colors',
        bordered && 'border border-gray-200',
        (variant === 'hoverable' || hoverable) && 'hover:border-gray-400',
        className
      )}
    >
      {title || extra ? (
        <header className="flex items-baseline justify-between gap-3 border-b border-gray-200 px-5 py-4">
          {title ? (
            <h2 className="font-display text-lg font-normal tracking-tight text-gray-900">
              {title}
            </h2>
          ) : null}
          {extra ? <div className="shrink-0">{extra}</div> : null}
        </header>
      ) : null}

      <div className="p-5">
        {loading ? (
          <div className="space-y-3" role="status" aria-label="加载中">
            {[0, 1, 2].map(index => (
              <div key={index} className="h-3 animate-pulse bg-gray-100" />
            ))}
          </div>
        ) : (
          children
        )}
      </div>

      {footer ? (
        <footer className="border-t border-gray-200 px-5 py-3 font-mono text-[11px] tracking-wide text-gray-500">
          {footer}
        </footer>
      ) : null}
    </section>
  )
}
