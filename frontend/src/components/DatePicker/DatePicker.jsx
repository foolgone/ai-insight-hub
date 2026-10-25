import clsx from 'clsx'
import { format, subDays } from 'date-fns'

/**
 * 日期范围选择（D-F20）：原生 date + 快捷范围，不引入日历库。
 * @param {{
 *   value?: { start?: string, end?: string },
 *   onChange?: (value: { start: string, end: string }) => void,
 *   disabled?: boolean,
 *   className?: string,
 * }} props
 */
export function DatePicker({ value, onChange, disabled = false, className }) {
  const start = value?.start || ''
  const end = value?.end || ''
  const invalid = Boolean(start && end && start > end)

  const emit = next => onChange?.({ start, end, ...next })

  const applyRecentDays = days => {
    const today = new Date()
    emit({
      start: format(subDays(today, days - 1), 'yyyy-MM-dd'),
      end: format(today, 'yyyy-MM-dd'),
    })
  }

  return (
    <div className={clsx('space-y-2', className)}>
      <div className="flex items-center gap-2">
        <input
          type="date"
          aria-label="开始日期"
          value={start}
          disabled={disabled}
          onChange={event => emit({ start: event.target.value })}
          className="h-10 rounded border border-gray-300 px-3 text-sm text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-50"
        />
        <span className="text-sm text-gray-400">至</span>
        <input
          type="date"
          aria-label="结束日期"
          value={end}
          disabled={disabled}
          onChange={event => emit({ end: event.target.value })}
          className="h-10 rounded border border-gray-300 px-3 text-sm text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:cursor-not-allowed disabled:bg-gray-50"
        />
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        {[
          { label: '最近 7 天', days: 7 },
          { label: '最近 30 天', days: 30 },
        ].map(item => (
          <button
            key={item.days}
            type="button"
            disabled={disabled}
            onClick={() => applyRecentDays(item.days)}
            className="rounded border border-gray-300 px-2 py-1 text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {item.label}
          </button>
        ))}
        <button
          type="button"
          disabled={disabled}
          onClick={() => emit({ start: '', end: '' })}
          className="rounded px-2 py-1 text-gray-500 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          清除
        </button>
      </div>

      {invalid ? (
        <p role="alert" className="text-xs text-error-600">
          开始日期不能晚于结束日期
        </p>
      ) : null}
    </div>
  )
}
