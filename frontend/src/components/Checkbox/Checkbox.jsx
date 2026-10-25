import { useId } from 'react'
import clsx from 'clsx'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { LuCheck, LuMinus } from 'react-icons/lu'

/**
 * 复选框（02 §2.4）：20×20、4px 圆角，支持 indeterminate。
 * @param {{
 *   checked?: boolean,
 *   onCheckedChange?: (checked: boolean|'indeterminate') => void,
 *   indeterminate?: boolean,
 *   disabled?: boolean,
 *   label?: string,
 *   id?: string,
 *   name?: string,
 *   value?: string,
 *   ariaLabel?: string,
 *   className?: string,
 * }} props
 */
export function Checkbox({
  checked = false,
  onCheckedChange,
  indeterminate = false,
  disabled = false,
  label,
  id,
  name,
  value,
  ariaLabel,
  className,
}) {
  const autoId = useId()
  const inputId = id || autoId

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <CheckboxPrimitive.Root
        id={inputId}
        name={name}
        value={value}
        checked={indeterminate ? 'indeterminate' : checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-label={ariaLabel}
        className={clsx(
          'flex h-5 w-5 shrink-0 items-center justify-center rounded border border-gray-300 bg-white text-white transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
          'data-[state=checked]:border-primary-500 data-[state=checked]:bg-primary-500',
          'data-[state=indeterminate]:border-primary-500 data-[state=indeterminate]:bg-primary-500',
          'disabled:cursor-not-allowed disabled:opacity-50'
        )}
      >
        <CheckboxPrimitive.Indicator>
          {indeterminate ? (
            <LuMinus className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <LuCheck className="h-3.5 w-3.5" aria-hidden="true" />
          )}
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {label ? (
        <label htmlFor={inputId} className="cursor-pointer text-sm text-gray-700">
          {label}
        </label>
      ) : null}
    </div>
  )
}
