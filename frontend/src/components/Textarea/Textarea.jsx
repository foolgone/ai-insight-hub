import { useId } from 'react'
import clsx from 'clsx'

/**
 * 多行输入框（02 §2.7）：Ctrl 不必要，`onChange` 只回传值。
 * @param {{
 *   value?: string,
 *   onChange?: (value: string) => void,
 *   placeholder?: string,
 *   error?: string,
 *   helperText?: string,
 *   maxLength?: number,
 *   rows?: number,
 *   disabled?: boolean,
 *   id?: string,
 *   className?: string,
 * }} props
 */
export function Textarea({
  value = '',
  onChange,
  placeholder,
  error,
  helperText,
  maxLength,
  rows = 4,
  disabled = false,
  id,
  className,
  ...rest
}) {
  const autoId = useId()
  const textareaId = id || autoId
  const messageId = `${textareaId}-message`
  const hasError = Boolean(error)

  return (
    <div className="w-full">
      <textarea
        id={textareaId}
        value={value}
        onChange={event => onChange?.(event.target.value)}
        placeholder={placeholder}
        rows={rows}
        maxLength={maxLength}
        disabled={disabled}
        aria-invalid={hasError || undefined}
        aria-describedby={error || helperText ? messageId : undefined}
        className={clsx(
          'min-h-20 w-full resize-y rounded border bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400',
          'focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:opacity-60',
          hasError
            ? 'border-error-500 focus:ring-error-500'
            : 'border-gray-300 focus:border-primary-500 focus:ring-primary-500',
          className
        )}
        {...rest}
      />
      {error || helperText || maxLength ? (
        <div className="mt-1 flex items-start justify-between gap-2 text-xs">
          <p
            id={messageId}
            role={hasError ? 'alert' : undefined}
            className={hasError ? 'text-error-600' : 'text-gray-500'}
          >
            {error || helperText || ''}
          </p>
          {maxLength ? (
            <span className="shrink-0 text-gray-400">
              {String(value).length}/{maxLength}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
