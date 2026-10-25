import clsx from 'clsx'
import { LuAlertTriangle, LuCheckCircle2, LuInfo, LuX } from 'react-icons/lu'

const VARIANTS = {
  success: {
    icon: LuCheckCircle2,
    wrapper: 'border-success-200 bg-success-50 text-success-700',
    iconClass: 'text-success-500',
  },
  info: {
    icon: LuInfo,
    wrapper: 'border-info-200 bg-info-50 text-info-700',
    iconClass: 'text-info-500',
  },
  warning: {
    icon: LuAlertTriangle,
    wrapper: 'border-warning-200 bg-warning-50 text-warning-700',
    iconClass: 'text-warning-500',
  },
  error: {
    icon: LuAlertTriangle,
    wrapper: 'border-error-200 bg-error-50 text-error-700',
    iconClass: 'text-error-500',
  },
}

/**
 * 警告提示（02 §4.4）。
 * @param {{
 *   variant?: 'success'|'info'|'warning'|'error',
 *   title?: string,
 *   children?: React.ReactNode,
 *   onClose?: () => void,
 *   className?: string,
 * }} props
 */
export function Alert({ variant = 'info', title, children, onClose, className }) {
  const meta = VARIANTS[variant] || VARIANTS.info
  const Icon = meta.icon

  return (
    <div
      role="alert"
      className={clsx(
        'flex min-h-12 items-start gap-3 rounded border px-4 py-3',
        meta.wrapper,
        className
      )}
    >
      <Icon className={clsx('mt-0.5 h-5 w-5 shrink-0', meta.iconClass)} aria-hidden="true" />
      <div className="min-w-0 flex-1 text-sm">
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? <div className={title ? 'mt-1' : ''}>{children}</div> : null}
      </div>
      {onClose ? (
        <button
          type="button"
          aria-label="关闭提示"
          onClick={onClose}
          className="shrink-0 rounded p-1 opacity-70 hover:opacity-100"
        >
          <LuX className="h-4 w-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  )
}
