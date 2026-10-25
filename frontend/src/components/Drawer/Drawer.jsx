import clsx from 'clsx'
import * as Dialog from '@radix-ui/react-dialog'
import { LuX } from 'react-icons/lu'

const POSITION_CLASSES = {
  right: 'inset-y-0 right-0 h-full',
  left: 'inset-y-0 left-0 h-full',
  top: 'inset-x-0 top-0 max-h-[80vh]',
  bottom: 'inset-x-0 bottom-0 max-h-[80vh]',
}

const SIZE_CLASSES = {
  sm: 'sm:max-w-[360px]',
  md: 'sm:max-w-[480px]',
  lg: 'sm:max-w-[600px]',
}

/**
 * 抽屉（02 §4.3）：默认右侧滑入，移动端全屏。
 * @param {{
 *   open: boolean,
 *   onClose: () => void,
 *   title: string,
 *   direction?: 'right'|'left'|'top'|'bottom',
 *   size?: 'sm'|'md'|'lg',
 *   footer?: React.ReactNode,
 *   children?: React.ReactNode,
 *   className?: string,
 * }} props
 */
export function Drawer({
  open,
  onClose,
  title,
  direction = 'right',
  size = 'md',
  footer,
  children,
  className,
}) {
  const isHorizontal = direction === 'right' || direction === 'left'

  return (
    <Dialog.Root open={open} onOpenChange={nextOpen => (nextOpen ? undefined : onClose())}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          aria-describedby={undefined}
          className={clsx(
            'fixed z-50 flex w-full flex-col bg-white shadow-xl focus:outline-none',
            POSITION_CLASSES[direction] || POSITION_CLASSES.right,
            isHorizontal ? SIZE_CLASSES[size] : null,
            className
          )}
        >
          <header className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-4">
            <Dialog.Title className="text-lg font-semibold text-gray-900">{title}</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="关闭"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-gray-500 hover:bg-gray-100"
              >
                <LuX className="h-4 w-4" aria-hidden="true" />
              </button>
            </Dialog.Close>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>

          {footer ? (
            <footer className="flex items-center justify-end gap-2 border-t border-gray-100 px-6 py-4">
              {footer}
            </footer>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
