import clsx from 'clsx'

const VARIANT_CLASSES = {
  default: 'border-gray-300 text-gray-600',
  success: 'border-success-500/30 bg-success-50 text-success-700',
  warning: 'border-warning-500/30 bg-warning-50 text-warning-700',
  error: 'border-error-500/30 bg-error-50 text-error-700',
  info: 'border-info-500/30 bg-info-50 text-info-700',
}

const SIZE_CLASSES = {
  sm: 'px-1.5 py-0.5 text-[11px]',
  md: 'px-2 py-1 text-xs',
}

/**
 * 徽章（编辑部风格）：细线描边 + 方角，替代彩色圆角胶囊。
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
        'inline-flex items-center rounded-none border font-medium tracking-wide',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className
      )}
    >
      {children}
    </span>
  )
}
