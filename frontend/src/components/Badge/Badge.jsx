import clsx from 'clsx'

const VARIANT_CLASSES = {
  default: 'bg-gray-100 text-gray-700',
  success: 'bg-success-50 text-success-700',
  warning: 'bg-warning-50 text-warning-700',
  error: 'bg-error-50 text-error-700',
  info: 'bg-info-50 text-info-700',
}

const SIZE_CLASSES = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1.5 text-sm',
}

/**
 * 徽章（02 §2.9）。
 * @param {{
 *   variant?: 'default'|'success'|'warning'|'error'|'info',
 *   size?: 'sm'|'md',
 *   className?: string,
 *   children?: React.ReactNode,
 * }} props
 */
export function Badge({ variant = 'default', size = 'md', className, children }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-sm font-medium',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className
      )}
    >
      {children}
    </span>
  )
}
