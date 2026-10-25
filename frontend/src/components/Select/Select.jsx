import { useId, useMemo, useState } from 'react'
import clsx from 'clsx'
import * as Popover from '@radix-ui/react-popover'
import { LuCheck, LuChevronDown, LuSearch } from 'react-icons/lu'

/**
 * 选择器（02 §2.3）：单选/多选/可搜索，点击外部或 Esc 关闭。
 * @param {{
 *   options: Array<{ label: string, value: string }>,
 *   value?: string|string[],
 *   onChange?: (value: string|string[]) => void,
 *   placeholder?: string,
 *   searchable?: boolean,
 *   multiple?: boolean,
 *   disabled?: boolean,
 *   error?: string,
 *   id?: string,
 *   name?: string,
 *   className?: string,
 * }} props
 */
export function Select({
  options = [],
  value,
  onChange,
  placeholder = '请选择',
  searchable = false,
  multiple = false,
  disabled = false,
  error,
  id,
  name,
  className,
}) {
  const autoId = useId()
  const triggerId = id || autoId
  const errorId = `${triggerId}-error`
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const selectedValues = multiple ? (Array.isArray(value) ? value : []) : value ? [value] : []
  const selectedOptions = options.filter(option => selectedValues.includes(option.value))
  const labelText = selectedOptions.map(option => option.label).join('、')

  const filteredOptions = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return options
    return options.filter(option => String(option.label).toLowerCase().includes(keyword))
  }, [options, query])

  const handleOpenChange = nextOpen => {
    if (disabled) return
    setOpen(nextOpen)
    if (!nextOpen) setQuery('')
  }

  const handleSelect = option => {
    if (multiple) {
      const nextValues = selectedValues.includes(option.value)
        ? selectedValues.filter(item => item !== option.value)
        : [...selectedValues, option.value]
      onChange?.(nextValues)
      return
    }
    onChange?.(option.value)
    setOpen(false)
  }

  return (
    <div className={clsx('w-full', className)}>
      <Popover.Root open={open} onOpenChange={handleOpenChange}>
        <Popover.Trigger asChild>
          <button
            id={triggerId}
            name={name}
            type="button"
            role="combobox"
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-invalid={Boolean(error) || undefined}
            aria-describedby={error ? errorId : undefined}
            disabled={disabled}
            className={clsx(
              'flex h-10 w-full items-center justify-between gap-2 rounded border bg-white px-3 text-left text-sm transition-colors',
              'focus-visible:outline-none focus-visible:ring-2',
              error
                ? 'border-error-500 focus-visible:ring-error-500'
                : 'border-gray-300 focus-visible:border-primary-500 focus-visible:ring-primary-500',
              disabled && 'cursor-not-allowed bg-gray-50 opacity-60'
            )}
          >
            <span className={clsx('truncate', labelText ? 'text-gray-900' : 'text-gray-400')}>
              {labelText || placeholder}
            </span>
            <LuChevronDown
              className={clsx(
                'h-4 w-4 shrink-0 text-gray-400 transition-transform',
                open && 'rotate-180'
              )}
              aria-hidden="true"
            />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content
            sideOffset={4}
            align="start"
            className="z-50 w-[var(--radix-popover-trigger-width)] rounded border border-gray-200 bg-white p-1 shadow-lg focus:outline-none"
          >
            {searchable ? (
              <div className="flex items-center gap-2 border-b border-gray-100 px-2 py-1.5">
                <LuSearch className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
                <input
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  placeholder="搜索选项"
                  aria-label="搜索选项"
                  className="h-7 w-full bg-transparent text-sm focus:outline-none"
                />
              </div>
            ) : null}
            <ul
              role="listbox"
              aria-multiselectable={multiple || undefined}
              className="max-h-64 overflow-y-auto py-1"
            >
              {filteredOptions.length === 0 ? (
                <li className="px-3 py-2 text-sm text-gray-400">无匹配选项</li>
              ) : (
                filteredOptions.map(option => {
                  const selected = selectedValues.includes(option.value)
                  return (
                    <li
                      key={option.value}
                      role="option"
                      aria-selected={selected}
                      onClick={() => handleSelect(option)}
                      className={clsx(
                        'flex cursor-pointer items-center justify-between gap-2 rounded px-3 py-2 text-sm',
                        selected
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-gray-700 hover:bg-gray-50'
                      )}
                    >
                      <span className="truncate">{option.label}</span>
                      {selected ? (
                        <LuCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
                      ) : null}
                    </li>
                  )
                })
              )}
            </ul>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      {error ? (
        <p id={errorId} role="alert" className="mt-1 text-xs text-error-600">
          {error}
        </p>
      ) : null}
    </div>
  )
}
