import clsx from 'clsx'
import * as Dialog from '@radix-ui/react-dialog'
import { LuX } from 'react-icons/lu'

const SIZE_CLASSES = {
  sm: 'md:max-w-[400px]',
  md: 'md:max-w-[600px]',
  lg: 'md:max-w-[800px]',
  xl: 'md:max-w-[1000px]',
}

/**
 * 模态框（02 §4.2）：基于 Radix Dialog，自带焦点陷阱/Esc/遮罩关闭。
 * @param {{
 *   open: boolean,
 *   onClose: () => void,
 *   title: string,
 *   size?: 'sm'|'md'|'lg'|'xl',
 *   footer?: React.ReactNode,
 *   children?: React.ReactNode,
 *   className?: string,
 * }} props
 */
export function Modal({ open, onClose, title, size = 'md', footer, children, className }) {
  return (
    <Dialog.Root open={open} onOpenChange={nextOpen => (nextOpen ? undefined : onClose())}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content
          aria-describedby={undefined}
          className={clsx(
            'fixed inset-0 z-50 flex flex-col bg-white p-6 focus:outline-none',
            'md:inset-auto md:left-1/2 md:top-1/2 md:h-auto md:max-h-[85vh] md:w-[calc(100%-2rem)] md:-translate-x-1/2 md:-translate-y-1/2 md:overflow-y-auto md:rounded-lg md:shadow-xl',
            SIZE_CLASSES[size],
            className
          )}
        >
          <header className="mb-4 flex items-start justify-between gap-4">
            <Dialog.Title className="text-lg font-semibold text-gray-900">{title}</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="关闭"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-gray-500 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
              >
                <LuX className="h-4 w-4" aria-hidden="true" />
              </button>
            </Dialog.Close>
          </header>

          <div className="min-h-0 flex-1 text-sm text-gray-700">{children}</div>

          {footer ? (
            <footer className="mt-6 flex flex-col-reverse gap-2 border-t border-gray-100 pt-4 sm:flex-row sm:justify-end">
              {footer}
            </footer>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
