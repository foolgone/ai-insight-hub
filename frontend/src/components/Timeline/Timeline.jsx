import clsx from 'clsx'

const DOT_CLASSES = {
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  error: 'bg-error-500',
  default: 'bg-gray-400',
}

/**
 * 时间线（02 §3.8）。
 * @param {{ items: Array<{ key?: string, title: string, time?: string, description?: string, status?: 'success'|'warning'|'error'|'default' }>, className?: string }} props
 */
export function Timeline({ items = [], className }) {
  return (
    <ol aria-label="时间线" className={clsx('space-y-4', className)}>
      {items.map((item, index) => {
        const status = DOT_CLASSES[item.status] ? item.status : 'default'
        return (
          <li key={item.key || item.title} className="relative flex gap-3 pl-1">
            {index < items.length - 1 ? (
              <span
                className="absolute left-[7px] top-4 h-[calc(100%-4px)] w-px bg-gray-300"
                aria-hidden="true"
              />
            ) : null}
            <span
              className={clsx('mt-1 h-3 w-3 shrink-0 rounded-full', DOT_CLASSES[status])}
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900">{item.title}</p>
              {item.time ? <p className="mt-0.5 text-xs text-gray-500">{item.time}</p> : null}
              {item.description ? (
                <p className="mt-1 text-sm text-gray-600">{item.description}</p>
              ) : null}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
