import { forwardRef } from 'react'
import clsx from 'clsx'

const VARIANT_CLASSES = {
  primary: 'bg-gray-900 text-gray-50 hover:bg-primary-600 active:bg-primary-700',
  secondary: 'bg-gray-100 text-gray-800 hover:bg-gray-200 active:bg-gray-300',
  outline:
    'border border-gray-300 bg-transparent text-gray-700 hover:border-gray-900 hover:text-gray-900 active:bg-gray-50',
  ghost: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 active:bg-gray-200',
  danger: 'bg-error-500 text-white hover:bg-error-600 active:bg-error-700',
}

const SIZE_CLASSES = {
  sm: 'h-8 gap-1.5 px-3 text-[12px]',
  md: 'h-9 gap-2 px-4 text-sm',
  lg: 'h-11 gap-2 px-6 text-sm',
}

/**
 * 按钮（编辑部风格）：直角、墨色主按钮、细线次按钮。
 * @typedef {'primary'|'secondary'|'outline'|'ghost'|'danger'} ButtonVariant
 * @typedef {'sm'|'md'|'lg'} ButtonSize
 */

/**
 * @param {{
 *   variant?: ButtonVariant,
 *   size?: ButtonSize,
 *   disabled?: boolean,
 *   loading?: boolean,
 *   icon?: React.ReactNode,
 *   iconRight?: React.ReactNode,
 *   fullWidth?: boolean,
 *   type?: 'button'|'submit'|'reset',
 *   className?: string,
 *   children?: React.ReactNode,
 *   onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void,
 * }} props
 */
export const Button = forwardRef(function Button(
  {
    variant = 'primary',
    size = 'md',
    disabled = false,
    loading = false,
    icon = null,
    iconRight = null,
    fullWidth = false,
    type = 'button',
    className,
    children,
    ...rest
  },
  ref
) {
  const isDisabled = disabled || loading

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={clsx(
        'inline-flex items-center justify-center rounded-sm font-medium tracking-wide transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-50',
        'disabled:cursor-not-allowed disabled:opacity-40',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        fullWidth && 'w-full',
        className
      )}
      {...rest}
    >
      {loading ? (
        <span
          className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      ) : icon ? (
        <span className="shrink-0" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children ? <span className="truncate">{children}</span> : null}
      {!loading && iconRight ? (
        <span className="shrink-0" aria-hidden="true">
          {iconRight}
        </span>
      ) : null}
    </button>
  )
})
