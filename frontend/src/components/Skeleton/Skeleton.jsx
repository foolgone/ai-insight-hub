import clsx from 'clsx'

/**
 * 骨架屏（02 §3.7）。
 * @param {{ variant?: 'text'|'card'|'table', rows?: number, className?: string }} props
 */
export function Skeleton({ variant = 'text', rows = 3, className }) {
  if (variant === 'card') {
    return (
      <div aria-hidden="true" className={clsx('space-y-3 rounded-md bg-white p-6', className)}>
        <div className="h-5 w-1/3 animate-pulse rounded bg-gray-200" />
        <div className="h-24 animate-pulse rounded bg-gray-100" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-gray-200" />
      </div>
    )
  }

  if (variant === 'table') {
    return (
      <div aria-hidden="true" className={clsx('space-y-2', className)}>
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="h-9 animate-pulse rounded bg-gray-100" />
        ))}
      </div>
    )
  }

  return (
    <div aria-hidden="true" className={clsx('space-y-2', className)}>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className={clsx('h-4 animate-pulse rounded bg-gray-200', index === rows - 1 && 'w-2/3')}
        />
      ))}
    </div>
  )
}
