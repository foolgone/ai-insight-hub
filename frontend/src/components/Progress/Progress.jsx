import clsx from 'clsx'

function colorClass(percent) {
  if (percent < 60) return 'text-error-500'
  if (percent < 80) return 'text-warning-500'
  return 'text-success-500'
}

/**
 * 进度条（02 §3.5）：line / circle / steps。
 * @param {{
 *   percent?: number,
 *   variant?: 'line'|'circle'|'steps',
 *   steps?: string[],
 *   current?: number,
 *   showPercent?: boolean,
 *   className?: string,
 * }} props
 */
export function Progress({
  percent = 0,
  variant = 'line',
  steps = [],
  current = 0,
  showPercent = false,
  className,
}) {
  const safePercent = Math.min(100, Math.max(0, Number(percent) || 0))

  if (variant === 'circle') {
    const radius = 45
    const circumference = 2 * Math.PI * radius
    const offset = circumference - (safePercent / 100) * circumference
    return (
      <svg
        role="img"
        aria-label={`进度 ${safePercent}%`}
        viewBox="0 0 100 100"
        className={clsx('h-24 w-24 -rotate-90', className)}
      >
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth="8"
          className="stroke-gray-200"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={clsx('transition-all', colorClass(safePercent))}
          style={{ stroke: 'currentColor' }}
        />
      </svg>
    )
  }

  if (variant === 'steps') {
    return (
      <ol aria-label="步骤进度" className={clsx('flex items-center gap-2', className)}>
        {steps.map((step, index) => {
          const done = index <= current
          return (
            <li key={step} className="flex items-center gap-2 text-xs">
              <span
                className={clsx(
                  'grid h-6 w-6 place-items-center rounded-full border',
                  done
                    ? 'border-primary-600 bg-primary-600 text-white'
                    : 'border-gray-300 bg-white text-gray-400'
                )}
                aria-hidden="true"
              >
                {index + 1}
              </span>
              <span className={done ? 'text-gray-900' : 'text-gray-400'}>{step}</span>
              {index < steps.length - 1 ? <span className="h-px w-6 bg-gray-200" /> : null}
            </li>
          )
        })}
      </ol>
    )
  }

  return (
    <div className={clsx('flex items-center gap-3', className)}>
      <div
        role="progressbar"
        aria-label="进度"
        aria-valuenow={safePercent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded-full bg-gray-200"
      >
        <div
          className={clsx('h-full rounded-full bg-current transition-all', colorClass(safePercent))}
          style={{ width: `${safePercent}%` }}
        />
      </div>
      {showPercent ? <span className="shrink-0 text-xs text-gray-600">{safePercent}%</span> : null}
    </div>
  )
}
