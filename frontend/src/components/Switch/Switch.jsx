import { useId } from 'react'
import clsx from 'clsx'
import * as SwitchPrimitive from '@radix-ui/react-switch'

/**
 * 开关（02 §2.6）：44×24，选中态 primary。
 * @param {{
 *   checked?: boolean,
 *   onCheckedChange?: (checked: boolean) => void,
 *   label?: string,
 *   disabled?: boolean,
 *   id?: string,
 *   className?: string,
 * }} props
 */
export function Switch({
  checked = false,
  onCheckedChange,
  label,
  disabled = false,
  id,
  className,
}) {
  const autoId = useId()
  const switchId = id || autoId

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <SwitchPrimitive.Root
        id={switchId}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-label={label ? undefined : '开关'}
        className={clsx(
          'relative h-6 w-11 shrink-0 rounded-full border border-transparent transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
          'data-[state=checked]:bg-primary-500 data-[state=unchecked]:bg-gray-300',
          'disabled:cursor-not-allowed disabled:opacity-50'
        )}
      >
        <SwitchPrimitive.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-5" />
      </SwitchPrimitive.Root>
      {label ? (
        <label htmlFor={switchId} className="cursor-pointer text-sm text-gray-700">
          {label}
        </label>
      ) : null}
    </div>
  )
}
