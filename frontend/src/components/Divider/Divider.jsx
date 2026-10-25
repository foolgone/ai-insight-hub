import clsx from 'clsx'

/**
 * 分割线（02 §2.12）。
 * @param {{ orientation?: 'horizontal'|'vertical', children?: React.ReactNode, className?: string }} props
 */
export function Divider({ orientation = 'horizontal', children, className }) {
  if (orientation === 'vertical') {
    return (
      <span
        role="separator"
        aria-orientation="vertical"
        className={clsx('mx-3 inline-block h-4 w-px bg-gray-200 align-middle', className)}
      />
    )
  }

  if (children) {
    return (
      <div
        role="separator"
        className={clsx('flex items-center gap-3 text-xs text-gray-400', className)}
      >
        <span className="h-px flex-1 bg-gray-200" />
        <span>{children}</span>
        <span className="h-px flex-1 bg-gray-200" />
      </div>
    )
  }

  return <div role="separator" className={clsx('h-px w-full bg-gray-200', className)} />
}
