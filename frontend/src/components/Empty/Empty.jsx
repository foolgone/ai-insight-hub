import clsx from 'clsx'

/**
 * 空状态（编辑部风格）：不放大图标，用衬线标题 + 等宽说明。
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
        'flex flex-col items-center justify-center gap-3 border border-dashed border-gray-300 px-6 py-14 text-center',
        className
      )}
    >
      {icon ? (
        <div className="text-gray-300" aria-hidden="true">
          {icon}
        </div>
      ) : (
        <div className="h-px w-10 bg-gray-300" aria-hidden="true" />
      )}
      <p className="font-display text-lg font-normal text-gray-700">{title}</p>
      {description ? (
        <p className="max-w-md font-mono text-[10px] uppercase leading-relaxed tracking-[0.16em] text-gray-400">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  )
}
