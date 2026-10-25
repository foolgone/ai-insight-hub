import { forwardRef } from 'react'
import clsx from 'clsx'

const VARIANT_CLASSES = {
  primary: 'bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-700',
  secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200 active:bg-gray-300',
  outline: 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 active:bg-gray-100',
  ghost: 'text-gray-600 hover:bg-gray-100 active:bg-gray-200',
  danger: 'bg-error-500 text-white hover:bg-error-600 active:bg-error-700',
}

const SIZE_CLASSES = {
  sm: 'h-8 gap-1.5 px-3 text-sm',
  md: 'h-10 gap-2 px-5 text-base',
  lg: 'h-12 gap-2 px-6 text-lg',
}

/**
 * @typedef {'primary'|'secondary'|'outline'|'ghost'|'danger'} ButtonVariant
 * @typedef {'sm'|'md'|'lg'} ButtonSize
 */

/**
 * 按钮（02 §2.1）。
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
        'inline-flex items-center justify-center rounded font-medium transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        fullWidth && 'w-full',
        className
      )}
      {...rest}
    >
      {loading ? (
        <span
          className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
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
