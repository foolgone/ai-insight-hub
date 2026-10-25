import { useId } from 'react'
import clsx from 'clsx'
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'

/**
 * 单选组（02 §2.5）：20×20 圆形，选中态外圈 primary + 内部实心圆。
 * @param {{
 *   options: Array<{ label: string, value: string, disabled?: boolean }>,
 *   value?: string,
 *   onChange?: (value: string) => void,
 *   disabled?: boolean,
 *   name?: string,
 *   ariaLabel?: string,
 *   className?: string,
 * }} props
 */
export function RadioGroup({
  options = [],
  value,
  onChange,
  disabled = false,
  name,
  ariaLabel = '单选组',
  className,
}) {
  const groupId = useId()

  return (
    <RadioGroupPrimitive.Root
      name={name}
      value={value}
      onValueChange={onChange}
      disabled={disabled}
      aria-label={ariaLabel}
      className={clsx('flex flex-col gap-2', className)}
    >
      {options.map(option => {
        const itemId = `${groupId}-${option.value}`
        return (
          <div key={option.value} className="flex items-center gap-2">
            <RadioGroupPrimitive.Item
              id={itemId}
              value={option.value}
              disabled={option.disabled}
              className={clsx(
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-gray-300 bg-white transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
                'data-[state=checked]:border-primary-500',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
            >
              <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
                <span className="h-2 w-2 rounded-full bg-primary-500" />
              </RadioGroupPrimitive.Indicator>
            </RadioGroupPrimitive.Item>
            <label
              htmlFor={itemId}
              className={clsx(
                'cursor-pointer text-sm',
                option.disabled || disabled ? 'cursor-not-allowed text-gray-400' : 'text-gray-700'
              )}
            >
              {option.label}
            </label>
          </div>
        )
      })}
    </RadioGroupPrimitive.Root>
  )
}
