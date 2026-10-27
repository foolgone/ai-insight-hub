import clsx from 'clsx'
import { LuChevronLeft, LuChevronRight } from 'react-icons/lu'

function buildPageItems(current, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const pages = new Set(
    [1, 2, totalPages - 1, totalPages, current - 1, current, current + 1].filter(
      page => page >= 1 && page <= totalPages
    )
  )
  const sorted = [...pages].sort((left, right) => left - right)
  const items = []

  sorted.forEach(page => {
    if (items.length > 0) {
      const previous = typeof items[items.length - 1] === 'number' ? items[items.length - 1] : 0
      if (page - previous > 1) items.push(`ellipsis-${page}`)
    }
    items.push(page)
  })

  return items
}

const BUTTON_CLASS =
  'flex h-8 min-w-8 items-center justify-center rounded border px-2 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50'

/**
 * 分页器（02 §5.4）。
 * @param {{
 *   current?: number,
 *   pageSize?: number,
 *   total?: number,
 *   onChange?: (page: number, pageSize: number) => void,
 *   className?: string,
 * }} props
 */
export function Pagination({ current = 1, pageSize = 20, total = 0, onChange, className }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const items = buildPageItems(current, totalPages)

  const go = page => {
    if (page < 1 || page > totalPages || page === current) return
    onChange?.(page, pageSize)
  }

  return (
    <nav
      aria-label="分页"
      className={clsx(
        'flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500',
        className
      )}
    >
      <span>共 {total} 条</span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="上一页"
          disabled={current <= 1}
          onClick={() => go(current - 1)}
          className={clsx(BUTTON_CLASS, 'border-gray-300 text-gray-600 hover:bg-gray-50')}
        >
          <LuChevronLeft className="h-4 w-4" aria-hidden="true" />
        </button>

        {items.map(item =>
          typeof item === 'number' ? (
            <button
              key={item}
              type="button"
              aria-label={`第 ${item} 页`}
              aria-current={item === current ? 'page' : undefined}
              onClick={() => go(item)}
              className={clsx(
                BUTTON_CLASS,
                item === current
                  ? 'border-primary-600 bg-primary-600 text-white'
                  : 'border-gray-300 text-gray-600 hover:bg-gray-50'
              )}
            >
              {item}
            </button>
          ) : (
            <span key={item} className="px-1 text-gray-400" aria-hidden="true">
              ...
            </span>
          )
        )}

        <button
          type="button"
          aria-label="下一页"
          disabled={current >= totalPages}
          onClick={() => go(current + 1)}
          className={clsx(BUTTON_CLASS, 'border-gray-300 text-gray-600 hover:bg-gray-50')}
        >
          <LuChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </nav>
  )
}
