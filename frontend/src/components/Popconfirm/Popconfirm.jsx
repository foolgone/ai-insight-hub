import { useState } from 'react'
import * as Popover from '@radix-ui/react-popover'
import { Button } from '../Button'

/**
 * 气泡确认框（02 §4.5）。
 * @param {{
 *   title: string,
 *   description?: string,
 *   onConfirm?: () => void,
 *   onCancel?: () => void,
 *   okText?: string,
 *   cancelText?: string,
 *   children: React.ReactElement,
 * }} props
 */
export function Popconfirm({
  title,
  description,
  onConfirm,
  onCancel,
  okText = '确认',
  cancelText = '取消',
  children,
}) {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>{children}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          className="z-50 w-72 rounded-md border border-gray-200 bg-white p-3 shadow-lg focus:outline-none"
        >
          <p className="text-sm font-medium text-gray-900">{title}</p>
          {description ? <p className="mt-1 text-xs text-gray-500">{description}</p> : null}
          <div className="mt-3 flex justify-end gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setOpen(false)
                onCancel?.()
              }}
            >
              {cancelText}
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setOpen(false)
                onConfirm?.()
              }}
            >
              {okText}
            </Button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
