import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as Popover from '@radix-ui/react-popover'
import clsx from 'clsx'
import { LuCheck, LuChevronDown, LuDatabase, LuPlus, LuSearch, LuSettings2 } from 'react-icons/lu'
import { useDataSourcesQuery } from '../../hooks/useDataSources'
import { useDatasourceStore } from '../../stores/datasourceStore'

const STATUS_META = {
  active: { label: '已就绪', dot: 'bg-success-500' },
  processing: { label: '处理中', dot: 'bg-warning-500' },
  archived: { label: '已归档', dot: 'bg-gray-400' },
  error: { label: '异常', dot: 'bg-error-500' },
}

const SELECTOR_PARAMS = { page: 1, limit: 100, sort: '-created_at' }

/**
 * Header 全局数据源选择器（D-F01 / F-106）。
 */
export function DataSourceSelector() {
  const navigate = useNavigate()
  const currentId = useDatasourceStore(state => state.currentId)
  const setCurrentId = useDatasourceStore(state => state.setCurrentId)
  const { data, isLoading, isError, refetch } = useDataSourcesQuery(SELECTOR_PARAMS)

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const items = useMemo(() => data?.items ?? [], [data])
  const current = items.find(item => item.id === currentId)

  useEffect(() => {
    if (items.length === 0) return
    if (!currentId || !items.some(item => item.id === currentId)) {
      setCurrentId(items[0].id)
    }
  }, [items, currentId, setCurrentId])

  const filteredItems = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return items
    return items.filter(item => String(item.name).toLowerCase().includes(keyword))
  }, [items, query])

  const handleOpenChange = nextOpen => {
    setOpen(nextOpen)
    if (!nextOpen) setQuery('')
  }

  const handleChoose = id => {
    setCurrentId(id)
    setOpen(false)
    setQuery('')
  }

  const goCreate = () => {
    setOpen(false)
    navigate('/data-sources?action=create')
  }

  const goManage = () => {
    setOpen(false)
    navigate('/data-sources')
  }

  const triggerLabel = isLoading
    ? '加载数据源...'
    : current
      ? current.name
      : isError
        ? '数据源加载失败'
        : '选择数据源'

  return (
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label="数据源选择器"
          className="flex h-9 max-w-[220px] items-center gap-2 rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-700 transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
        >
          <LuDatabase className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
          <span className="truncate">{triggerLabel}</span>
          <LuChevronDown className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          sideOffset={6}
          align="end"
          className="z-50 w-72 rounded-md border border-gray-200 bg-white shadow-lg focus:outline-none"
        >
          {isError ? (
            <div className="flex items-center justify-between gap-2 p-3 text-sm text-error-600">
              数据源加载失败
              <button
                type="button"
                onClick={() => refetch()}
                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
              >
                重试
              </button>
            </div>
          ) : (
            <>
              {items.length > 4 ? (
                <div className="flex items-center gap-2 border-b border-gray-100 px-2 py-1.5">
                  <LuSearch className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
                  <input
                    value={query}
                    onChange={event => setQuery(event.target.value)}
                    placeholder="搜索数据源"
                    aria-label="搜索数据源"
                    className="h-7 w-full bg-transparent text-sm focus:outline-none"
                  />
                </div>
              ) : null}

              <ul role="listbox" aria-label="数据源列表" className="max-h-64 overflow-y-auto p-1">
                {filteredItems.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-gray-400">
                    {items.length === 0 ? '暂无数据源' : '无匹配数据源'}
                  </li>
                ) : (
                  filteredItems.map(item => {
                    const status = STATUS_META[item.status] || {
                      label: item.status,
                      dot: 'bg-gray-400',
                    }
                    const selected = item.id === currentId
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={selected}
                          onClick={() => handleChoose(item.id)}
                          className={clsx(
                            'flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm',
                            selected
                              ? 'bg-primary-50 text-primary-700'
                              : 'text-gray-700 hover:bg-gray-50'
                          )}
                        >
                          <span
                            className={clsx('h-2 w-2 shrink-0 rounded-full', status.dot)}
                            aria-hidden="true"
                          />
                          <span className="min-w-0 flex-1 truncate">{item.name}</span>
                          <span className="shrink-0 text-xs text-gray-400">{status.label}</span>
                          {selected ? (
                            <LuCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
                          ) : null}
                        </button>
                      </li>
                    )
                  })
                )}
              </ul>

              <div className="border-t border-gray-100 p-1">
                <button
                  type="button"
                  onClick={goCreate}
                  className="flex w-full items-center gap-2 rounded px-2 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <LuPlus className="h-4 w-4" aria-hidden="true" />
                  新建数据源
                </button>
                <button
                  type="button"
                  onClick={goManage}
                  className="flex w-full items-center gap-2 rounded px-2 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <LuSettings2 className="h-4 w-4" aria-hidden="true" />
                  管理数据源
                </button>
              </div>
            </>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
