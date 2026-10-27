import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LuPlus, LuRefreshCw } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Select } from '../../components/Select'
import { DataSourceCard } from '../../components/business/DataSourceCard'
import { CreateDataSourceDrawer } from '../../components/datasource/CreateDataSourceDrawer'
import { DataSourceActions } from '../../components/datasource/DataSourceActions'
import { DataSourceDetailDrawer } from '../../components/datasource/DataSourceDetailDrawer'
import { DeleteDataSourceModal } from '../../components/datasource/DeleteDataSourceModal'
import { EditDataSourceModal } from '../../components/datasource/EditDataSourceModal'
import { UploadDataModal } from '../../components/datasource/UploadDataModal'
import { useDataSourcesQuery } from '../../hooks/useDataSources'
import { usePermissions } from '../../hooks/usePermissions'

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { label: '全部状态', value: 'all' },
  { label: '处理中', value: 'processing' },
  { label: '已就绪', value: 'active' },
  { label: '已归档', value: 'archived' },
  { label: '异常', value: 'error' },
]

const TYPE_OPTIONS = [
  { label: '全部类型', value: 'all' },
  { label: '客服对话', value: 'customer_service' },
  { label: '销售', value: 'sales' },
  { label: '支持', value: 'support' },
  { label: '其他', value: 'other' },
]

export default function DataSources() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const createOpen = searchParams.get('action') === 'create'

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [keyword, setKeyword] = useState('')
  const [detailTarget, setDetailTarget] = useState(null)
  const [editTarget, setEditTarget] = useState(null)
  const [uploadTarget, setUploadTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const { canWrite } = usePermissions()

  const params = useMemo(
    () => ({
      page,
      limit: PAGE_SIZE,
      sort: '-created_at',
      ...(status ? { status } : {}),
      ...(type ? { type } : {}),
    }),
    [page, status, type]
  )

  const query = useDataSourcesQuery(params)
  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const pagination = query.data?.pagination
  const totalPages = Math.max(1, Math.ceil((pagination?.total ?? 0) / PAGE_SIZE))

  const filteredItems = useMemo(() => {
    const search = keyword.trim().toLowerCase()
    if (!search) return items
    return items.filter(item => String(item.name).toLowerCase().includes(search))
  }, [items, keyword])

  const openCreate = () => setSearchParams({ action: 'create' })
  const closeCreate = () => setSearchParams({})

  const handleCreated = () => {
    setSearchParams({})
    query.refetch()
    navigate('/data-cleaning')
  }

  return (
    <section>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">数据源管理</h1>
          <p className="mt-1 text-sm text-gray-500">
            按数据源隔离导入与分析，支持 CSV / JSON / XLSX / TXT（≤ 50MB）
          </p>
        </div>
        {canWrite ? (
          <Button icon={<LuPlus className="h-4 w-4" />} onClick={openCreate}>
            新建数据源
          </Button>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          type="search"
          value={keyword}
          onChange={value => {
            setKeyword(value)
            setPage(1)
          }}
          placeholder="搜索当前页数据源名称"
          aria-label="搜索数据源名称"
        />
        <Select
          ariaLabel="数据源状态筛选"
          options={STATUS_OPTIONS}
          value={status || 'all'}
          onChange={value => {
            setStatus(value === 'all' ? '' : value)
            setPage(1)
          }}
        />
        <Select
          ariaLabel="数据源类型筛选"
          options={TYPE_OPTIONS}
          value={type || 'all'}
          onChange={value => {
            setType(value === 'all' ? '' : value)
            setPage(1)
          }}
        />
        <Button
          variant="outline"
          icon={<LuRefreshCw className="h-4 w-4" />}
          onClick={() => query.refetch()}
        >
          刷新
        </Button>
      </div>

      <div className="mt-4 overflow-hidden rounded-md border border-gray-200 bg-white">
        {query.isLoading ? <PageLoading label="正在加载数据源..." /> : null}

        {query.isError ? (
          <div className="p-4">
            <AsyncState error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : null}

        {!query.isLoading && !query.isError ? (
          filteredItems.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-sm text-gray-500">
                {items.length === 0 ? '暂无数据源，先创建一个吧' : '当前页无匹配数据源'}
              </p>
              {canWrite && items.length === 0 ? (
                <Button className="mt-4" icon={<LuPlus className="h-4 w-4" />} onClick={openCreate}>
                  新建数据源
                </Button>
              ) : null}
            </div>
          ) : (
            filteredItems.map(datasource => (
              <DataSourceCard
                key={datasource.id}
                datasource={datasource}
                actions={
                  <DataSourceActions
                    datasource={datasource}
                    canWrite={canWrite}
                    onDetail={() => setDetailTarget(datasource)}
                    onEdit={() => setEditTarget(datasource)}
                    onUpload={() => setUploadTarget(datasource)}
                    onDelete={() => setDeleteTarget(datasource)}
                  />
                }
              />
            ))
          )
        ) : null}
      </div>

      {pagination && pagination.total > 0 ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
          <span>共 {pagination.total} 条</span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage(current => Math.max(1, current - 1))}
            >
              上一页
            </Button>
            <span>
              第 {page} / {totalPages} 页
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages}
              onClick={() => setPage(current => current + 1)}
            >
              下一页
            </Button>
          </div>
        </div>
      ) : null}

      <CreateDataSourceDrawer open={createOpen} onClose={closeCreate} onSuccess={handleCreated} />

      <DataSourceDetailDrawer
        datasource={detailTarget}
        open={Boolean(detailTarget)}
        onClose={() => setDetailTarget(null)}
      />
      <EditDataSourceModal
        datasource={editTarget}
        open={Boolean(editTarget)}
        onClose={() => setEditTarget(null)}
      />
      <UploadDataModal
        datasource={uploadTarget}
        open={Boolean(uploadTarget)}
        onClose={() => setUploadTarget(null)}
      />
      <DeleteDataSourceModal
        datasource={deleteTarget}
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
      />
    </section>
  )
}
