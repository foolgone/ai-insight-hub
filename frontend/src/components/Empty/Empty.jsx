import clsx from 'clsx'
import { LuInbox } from 'react-icons/lu'

/**
 * 空状态（02 §3.6）。
 * @param {{
 *   icon?: React.ReactNode,
 *   title?: string,
 *   description?: string,
 *   action?: React.ReactNode,
 *   className?: string,
 * }} props
 */
export function Empty({ icon, title = '暂无数据', description, action, className }) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-gray-300 bg-white px-6 py-10 text-center',
        className
      )}
    >
      <div className="text-gray-300" aria-hidden="true">
        {icon || <LuInbox className="h-12 w-12" />}
      </div>
      <p className="text-base text-gray-600">{title}</p>
      {description ? <p className="text-sm text-gray-500">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}
