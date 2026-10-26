import { useState } from 'react'
import clsx from 'clsx'
import { Checkbox } from '../Checkbox'

function resolveRowKey(record, rowKey) {
  return typeof rowKey === 'function' ? rowKey(record) : record[rowKey]
}

function compareValues(left, right) {
  if (left === right) return 0
  if (left === null || left === undefined) return -1
  if (right === null || right === undefined) return 1
  if (typeof left === 'number' && typeof right === 'number') return left - right
  return String(left).localeCompare(String(right), 'zh-CN')
}

/**
 * 表格（02 §3.1）：排序/分页/多选/固定列/空态/加载态。
 * @param {{
 *   columns: Array<{
 *     key: string,
 *     title: string,
 *     dataIndex?: string,
 *     width?: number,
 *     sortable?: boolean,
 *     fixed?: 'left',
 *     render?: (value: any, record: any) => React.ReactNode,
 *   }>,
 *   dataSource?: Object[],
 *   rowKey?: string|((record: Object) => string),
 *   loading?: boolean,
 *   pagination?: { current: number, pageSize: number, total: number, onChange: (page: number, pageSize: number) => void },
 *   rowSelection?: { selectedRowKeys: string[], onChange: (keys: string[]) => void },
 *   caption?: string,
 *   emptyText?: string,
 *   className?: string,
 * }} props
 */
export function Table({
  columns = [],
  dataSource = [],
  rowKey = 'id',
  loading = false,
  pagination,
  rowSelection,
  caption = '数据表格',
  emptyText = '暂无数据',
  className,
}) {
  const [sort, setSort] = useState(null)

  const sortedData = (() => {
    if (!sort) return dataSource
    const column = columns.find(item => item.key === sort.key)
    if (!column?.dataIndex) return dataSource
    const direction = sort.direction === 'asc' ? 1 : -1
    return [...dataSource].sort(
      (left, right) => compareValues(left[column.dataIndex], right[column.dataIndex]) * direction
    )
  })()

  const pageKeys = dataSource.map(record => resolveRowKey(record, rowKey))
  const selectedKeys = rowSelection?.selectedRowKeys || []
  const allSelected = pageKeys.length > 0 && pageKeys.every(key => selectedKeys.includes(key))
  const someSelected = !allSelected && pageKeys.some(key => selectedKeys.includes(key))
  const columnCount = columns.length + (rowSelection ? 1 : 0)

  const toggleAll = checked => {
    if (!rowSelection) return
    const nextKeys = checked
      ? Array.from(new Set([...selectedKeys, ...pageKeys]))
      : selectedKeys.filter(key => !pageKeys.includes(key))
    rowSelection.onChange(nextKeys)
  }

  const toggleRow = (key, checked) => {
    if (!rowSelection) return
    const nextKeys = checked
      ? Array.from(new Set([...selectedKeys, key]))
      : selectedKeys.filter(item => item !== key)
    rowSelection.onChange(nextKeys)
  }

  const toggleSort = column => {
    setSort(current => {
      if (current?.key !== column.key) return { key: column.key, direction: 'asc' }
      if (current.direction === 'asc') return { key: column.key, direction: 'desc' }
      return null
    })
  }

  const totalPages = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.pageSize)) : 1

  return (
    <div className={clsx('overflow-hidden rounded-md border border-gray-200 bg-white', className)}>
      <div className="overflow-x-auto">
        <table aria-busy={loading || undefined} className="min-w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-gray-50 text-left text-gray-700">
            <tr>
              {rowSelection ? (
                <th scope="col" className="w-12 px-4 py-3">
                  <Checkbox
                    ariaLabel="全选当前页"
                    checked={allSelected}
                    indeterminate={someSelected}
                    onCheckedChange={toggleAll}
                  />
                </th>
              ) : null}
              {columns.map(column => (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    column.sortable
                      ? sort?.key === column.key
                        ? sort.direction === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                      : undefined
                  }
                  style={column.width ? { width: column.width } : undefined}
                  className={clsx(
                    'whitespace-nowrap px-4 py-3 font-semibold',
                    column.fixed === 'left' && 'sticky left-0 z-10 bg-gray-50'
                  )}
                >
                  {column.sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column)}
                      className="inline-flex items-center gap-1 hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
                    >
                      {column.title}
                      <span aria-hidden="true" className="text-xs text-gray-400">
                        {sort?.key !== column.key ? '↕' : sort.direction === 'asc' ? '↑' : '↓'}
                      </span>
                      <span className="sr-only">
                        {sort?.key === column.key
                          ? sort.direction === 'asc'
                            ? '当前升序，点击切换降序'
                            : '当前降序，点击取消排序'
                          : '点击升序排序'}
                      </span>
                    </button>
                  ) : (
                    column.title
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              Array.from({ length: 5 }).map((_, index) => (
                <tr key={`skeleton-${index}`}>
                  <td colSpan={columnCount} className="px-4 py-3">
                    <div className="h-5 animate-pulse rounded bg-gray-200" />
                  </td>
                </tr>
              ))
            ) : sortedData.length === 0 ? (
              <tr>
                <td colSpan={columnCount} className="px-4 py-10 text-center text-gray-500">
                  {emptyText}
                </td>
              </tr>
            ) : (
              sortedData.map(record => {
                const key = resolveRowKey(record, rowKey)
                return (
                  <tr key={key} className="hover:bg-gray-50">
                    {rowSelection ? (
                      <td className="px-4 py-3">
                        <Checkbox
                          ariaLabel={`选择 ${key}`}
                          checked={selectedKeys.includes(key)}
                          onCheckedChange={checked => toggleRow(key, checked)}
                        />
                      </td>
                    ) : null}
                    {columns.map(column => (
                      <td
                        key={column.key}
                        className={clsx(
                          'px-4 py-3 text-gray-700',
                          column.fixed === 'left' && 'sticky left-0 z-10 bg-white'
                        )}
                      >
                        {column.render
                          ? column.render(
                              column.dataIndex ? record[column.dataIndex] : record,
                              record
                            )
                          : column.dataIndex
                            ? record[column.dataIndex]
                            : null}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {pagination && pagination.total > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 px-4 py-2 text-xs text-gray-500">
          <span>共 {pagination.total} 条</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="上一页"
              disabled={pagination.current <= 1}
              onClick={() => pagination.onChange(pagination.current - 1, pagination.pageSize)}
              className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
            >
              上一页
            </button>
            <span>
              第 {pagination.current} / {totalPages} 页
            </span>
            <button
              type="button"
              aria-label="下一页"
              disabled={pagination.current >= totalPages}
              onClick={() => pagination.onChange(pagination.current + 1, pagination.pageSize)}
              className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
