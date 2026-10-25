import { useId } from 'react'
import clsx from 'clsx'
import { LuSearch } from 'react-icons/lu'

/**
 * 输入框（02 §2.2）：`onChange` 只回传值；错误/辅助文本自动关联 aria。
 * @param {{
 *   type?: 'text'|'email'|'password'|'number'|'search',
 *   value?: string,
 *   onChange?: (value: string) => void,
 *   placeholder?: string,
 *   error?: string,
 *   helperText?: string,
 *   prefix?: React.ReactNode,
 *   suffix?: React.ReactNode,
 *   disabled?: boolean,
 *   required?: boolean,
 *   id?: string,
 *   name?: string,
 *   className?: string,
 * }} props
 */
export function Input({
  type = 'text',
  value,
  onChange,
  placeholder,
  error,
  helperText,
  prefix = null,
  suffix = null,
  disabled = false,
  required = false,
  id,
  name,
  className,
  ...rest
}) {
  const autoId = useId()
  const inputId = id || autoId
  const messageId = `${inputId}-message`
  const hasError = Boolean(error)
  const showSearchIcon = type === 'search' && !prefix

  return (
    <div className="w-full">
      <div
        className={clsx(
          'flex h-10 items-center gap-2 rounded border bg-white px-3 transition-colors focus-within:ring-2',
          hasError
            ? 'border-error-500 focus-within:ring-error-500'
            : 'border-gray-300 focus-within:border-primary-500 focus-within:ring-primary-500',
          disabled && 'cursor-not-allowed bg-gray-50 opacity-60'
        )}
      >
        {showSearchIcon ? (
          <LuSearch className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
        ) : null}
        {prefix ? (
          <span className="shrink-0 text-gray-400" aria-hidden="true">
            {prefix}
          </span>
        ) : null}
        <input
          id={inputId}
          name={name}
          type={type}
          value={value}
          onChange={event => onChange?.(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          aria-invalid={hasError || undefined}
          aria-describedby={error || helperText ? messageId : undefined}
          className={clsx(
            'h-full w-full min-w-0 bg-transparent text-sm text-gray-900 placeholder:text-gray-400',
            'focus:outline-none disabled:cursor-not-allowed',
            className
          )}
          {...rest}
        />
        {suffix ? (
          <span className="shrink-0 text-gray-400" aria-hidden="true">
            {suffix}
          </span>
        ) : null}
      </div>
      {error || helperText ? (
        <p
          id={messageId}
          role={hasError ? 'alert' : undefined}
          className={clsx('mt-1 text-xs', hasError ? 'text-error-600' : 'text-gray-500')}
        >
          {error || helperText}
        </p>
      ) : null}
    </div>
  )
}
