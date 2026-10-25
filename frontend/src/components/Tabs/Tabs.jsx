import { useState } from 'react'
import clsx from 'clsx'

/**
 * 标签页（02 §5.3）：line 风格，支持受控/非受控。
 * @param {{
 *   items: Array<{ key: string, label: string, count?: number }>,
 *   value?: string,
 *   defaultValue?: string,
 *   onChange?: (key: string) => void,
 *   className?: string,
 * }} props
 */
export function Tabs({ items = [], value, defaultValue, onChange, className }) {
  const [innerValue, setInnerValue] = useState(defaultValue ?? items[0]?.key)
  const activeValue = value ?? innerValue

  const handleSelect = key => {
    if (value === undefined) setInnerValue(key)
    onChange?.(key)
  }

  return (
    <div
      role="tablist"
      aria-label="标签页"
      className={clsx('flex gap-4 border-b border-gray-200', className)}
    >
      {items.map(item => {
        const active = item.key === activeValue
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => handleSelect(item.key)}
            className={clsx(
              '-mb-px flex items-center gap-1.5 border-b-2 px-1 py-2.5 text-sm transition-colors',
              active
                ? 'border-primary-500 font-medium text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-900'
            )}
          >
            {item.label}
            {item.count !== undefined && item.count !== null ? (
              <span
                className={clsx(
                  'rounded-full px-1.5 py-0.5 text-xs',
                  active ? 'bg-primary-50 text-primary-700' : 'bg-gray-100 text-gray-500'
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
