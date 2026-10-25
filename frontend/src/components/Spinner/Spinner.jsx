import clsx from 'clsx'

const SIZE_CLASSES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
}

/**
 * 加载指示器（02 §4.6）。
 * @param {{ size?: 'sm'|'md'|'lg', label?: string, className?: string }} props
 */
export function Spinner({ size = 'md', label = '加载中', className }) {
  return (
    <span
      role="status"
      aria-label={label}
      className={clsx(
        'inline-block animate-spin rounded-full border-primary-500 border-t-transparent',
        SIZE_CLASSES[size],
        className
      )}
    />
  )
}
