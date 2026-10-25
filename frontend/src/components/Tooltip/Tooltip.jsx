import * as TooltipPrimitive from '@radix-ui/react-tooltip'

/**
 * 工具提示（02 §2.11）：300ms 延迟，深色气泡。
 * @param {{
 *   content: React.ReactNode,
 *   children: React.ReactElement,
 *   side?: 'top'|'right'|'bottom'|'left',
 * }} props
 */
export function Tooltip({ content, children, side = 'top' }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            className="z-50 max-w-[200px] rounded bg-gray-900 px-2.5 py-1.5 text-xs text-white shadow-md"
          >
            {content}
            <TooltipPrimitive.Arrow className="fill-gray-900" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}
