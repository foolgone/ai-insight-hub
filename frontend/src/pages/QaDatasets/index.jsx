import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  LuChevronRight,
  LuFileText,
  LuFlaskConical,
  LuPencil,
  LuPlus,
  LuRefreshCw,
  LuSend,
  LuTrash2,
  LuUpload,
} from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { PageHeader } from '../../components/common/PageHeader'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Input } from '../../components/Input'
import { Pagination } from '../../components/Pagination'
import { Popconfirm } from '../../components/Popconfirm'
import { Table } from '../../components/Table'
import { CreateDatasetModal } from '../../components/qaDataset/CreateDatasetModal'
import { CreateVersionModal } from '../../components/qaDataset/CreateVersionModal'
import { EditItemModal } from '../../components/qaDataset/EditItemModal'
import { ImportItemsModal } from '../../components/qaDataset/ImportItemsModal'
import { PublishVersionModal } from '../../components/qaDataset/PublishVersionModal'
import { deleteQaDatasetItem } from '../../api/qaDatasets'
import {
  qaDatasetKeys,
  useQaDatasetItemsQuery,
  useQaDatasetQuery,
  useQaDatasetStatsQuery,
  useQaDatasetsQuery,
} from '../../hooks/useQaDatasets'
import { usePermissions } from '../../hooks/usePermissions'
import { getErrorMessage } from '../../lib/errorMessages'
import { formatDateTime } from '../../lib/format'
import { notify } from '../../lib/toast'

const PAGE_SIZE = 20
const ITEM_PAGE_SIZE = 10

const SOURCE_META = {
  mixed: { label: '混合', variant: 'info' },
  doc: { label: '文档', variant: 'default' },
  conv: { label: '对话', variant: 'success' },
}

const VERSION_STATUS_META = {
  draft: { label: '草稿', variant: 'warning' },
  published: { label: '已发布', variant: 'success' },
  archived: { label: '已归档', variant: 'default' },
}

const SPLIT_LABELS = {
  train: 'train',
  valid: 'valid',
  test: 'test',
}

function sourceBadge(sourceType) {
  const meta = SOURCE_META[sourceType] || { label: sourceType, variant: 'default' }
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

function versionBadge(status) {
  const meta = VERSION_STATUS_META[status] || { label: status, variant: 'default' }
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

function percent(value) {
  const number = Number(value) || 0
  return `${Math.round(number * 1000) / 10}%`
}

export default function QaDatasets() {
  const { canWrite } = usePermissions()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [page, setPage] = useState(1)
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [selectedVersionId, setSelectedVersionId] = useState(null)
  const [itemPage, setItemPage] = useState(1)

  const [createDatasetOpen, setCreateDatasetOpen] = useState(false)
  const [createVersionOpen, setCreateVersionOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [publishTarget, setPublishTarget] = useState(null)
  const [editItem, setEditItem] = useState(null)

  const listParams = useMemo(
    () => ({ page, limit: PAGE_SIZE, ...(keyword ? { keyword } : {}) }),
    [page, keyword]
  )
  const listQuery = useQaDatasetsQuery(listParams)
  const datasets = useMemo(() => listQuery.data?.items ?? [], [listQuery.data])
  const listPagination = listQuery.data?.pagination
  const totalPages = Math.max(1, Math.ceil((listPagination?.total ?? 0) / PAGE_SIZE))

  const detailQuery = useQaDatasetQuery(selectedId)
  const versions = useMemo(() => detailQuery.data?.versions ?? [], [detailQuery.data])
  const selectedVersion = versions.find(version => version.id === selectedVersionId) || null

  const statsQuery = useQaDatasetStatsQuery(selectedId, selectedVersionId)
  const itemsQuery = useQaDatasetItemsQuery(selectedId, selectedVersionId, {
    page: itemPage,
    limit: ITEM_PAGE_SIZE,
  })
  const items = useMemo(() => itemsQuery.data?.items ?? [], [itemsQuery.data])
  const itemsPagination = itemsQuery.data?.pagination

  useEffect(() => {
    // 只在首次进入且未选择时自动选第一个；创建后不要被旧列表回拉，
    // 否则会切换数据集并导致“版本/数据集不匹配”的 404。
    if (selectedId || !datasets.length) return
    setSelectedId(datasets[0].id)
  }, [datasets, selectedId])

  useEffect(() => {
    setSelectedVersionId(null)
    setItemPage(1)
  }, [selectedId])

  useEffect(() => {
    if (!versions.length) {
      if (selectedVersionId) setSelectedVersionId(null)
      return
    }
    if (!versions.some(version => version.id === selectedVersionId)) {
      setSelectedVersionId(versions[0].id)
    }
  }, [versions, selectedVersionId])

  const refreshSelected = async () => {
    await Promise.all([detailQuery.refetch(), statsQuery.refetch(), itemsQuery.refetch()])
  }

  const handleDatasetCreated = async created => {
    setKeyword('')
    setKeywordInput('')
    setPage(1)
    setSelectedId(created.id)
    queryClient.invalidateQueries({ queryKey: qaDatasetKeys.all })
    notify.success(`已创建数据集「${created.name}」`)
  }

  const handleVersionCreated = async created => {
    await detailQuery.refetch()
    setSelectedVersionId(created.id)
    setItemPage(1)
    notify.success(`已创建草稿版本 v${created.version}`)
  }

  const handleImported = async result => {
    await refreshSelected()
    notify.success(`已导入 ${result.imported} 条；当前版本 ${result.version_item_count} 条`)
  }

  const handlePublished = async published => {
    await Promise.all([detailQuery.refetch(), statsQuery.refetch()])
    notify.success(`v${published.version} 已发布，发布后不可修改`)
  }

  const handleItemSaved = async () => {
    await Promise.all([itemsQuery.refetch(), statsQuery.refetch(), detailQuery.refetch()])
    notify.success('条目已更新')
  }

  const handleDeleteItem = async item => {
    try {
      await deleteQaDatasetItem(selectedId, selectedVersionId, item.id)
      await Promise.all([itemsQuery.refetch(), statsQuery.refetch(), detailQuery.refetch()])
      notify.success(`已删除条目 ${item.item_key}`)
    } catch (err) {
      notify.error(getErrorMessage(err))
    }
  }

  const handleSearch = event => {
    event.preventDefault()
    setKeyword(keywordInput.trim())
    setPage(1)
  }

  const itemColumns = [
    {
      key: 'item_key',
      title: 'Key',
      dataIndex: 'item_key',
      width: 120,
      render: value => <span className="font-mono text-xs text-gray-700">{value}</span>,
    },
    {
      key: 'query',
      title: 'Query',
      dataIndex: 'query',
      render: value => <p className="max-w-[360px] truncate text-sm text-gray-900">{value}</p>,
    },
    {
      key: 'split',
      title: 'Split',
      dataIndex: 'split',
      width: 80,
      render: value => (
        <span className="font-mono text-[11px]">{SPLIT_LABELS[value] || value}</span>
      ),
    },
    {
      key: 'category',
      title: '分类',
      dataIndex: 'category',
      width: 100,
      render: value => value || '—',
    },
    {
      key: 'evidence',
      title: '证据',
      render: (_, record) => `${(record.gold_evidence || []).length} 条`,
    },
    {
      key: 'actions',
      title: '操作',
      width: 110,
      render: (_, record) =>
        canWrite && selectedVersion?.status === 'draft' ? (
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="ghost"
              aria-label={`编辑 ${record.item_key}`}
              onClick={() => setEditItem(record)}
              icon={<LuPencil className="h-3.5 w-3.5" />}
            />
            <Popconfirm
              title="删除该条目？"
              description={`${record.item_key} 删除后不可恢复。`}
              onConfirm={() => handleDeleteItem(record)}
              okText="删除"
            >
              <Button
                size="sm"
                variant="ghost"
                aria-label={`删除 ${record.item_key}`}
                icon={<LuTrash2 className="h-3.5 w-3.5" />}
              />
            </Popconfirm>
          </div>
        ) : (
          <span className="text-xs text-gray-400">只读</span>
        ),
    },
  ]

  return (
    <section>
      <PageHeader
        index="04A"
        eyebrow="QA Datasets"
        title="QA 数据集"
        description="自建评测集：创建数据集、维护草稿版本、导入/校验条目、发布后发起 RAG 评测。"
        actions={
          canWrite ? (
            <Button
              icon={<LuPlus className="h-4 w-4" />}
              onClick={() => setCreateDatasetOpen(true)}
            >
              新建数据集
            </Button>
          ) : null
        }
      />

      <div className="mt-4 grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="border border-gray-200 bg-white">
          <form
            onSubmit={handleSearch}
            className="flex items-center gap-2 border-b border-gray-100 p-3"
          >
            <Input
              type="search"
              value={keywordInput}
              onChange={setKeywordInput}
              placeholder="搜索数据集名称"
              aria-label="搜索数据集名称"
            />
            <Button type="submit" size="sm" variant="outline">
              搜索
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label="刷新数据集列表"
              onClick={() => listQuery.refetch()}
              icon={<LuRefreshCw className="h-4 w-4" />}
            />
          </form>

          {listQuery.isLoading ? (
            <div className="p-4">
              <PageLoading label="正在加载数据集..." />
            </div>
          ) : listQuery.isError ? (
            <div className="p-4">
              <AsyncState error={listQuery.error} onRetry={() => listQuery.refetch()} />
            </div>
          ) : datasets.length === 0 ? (
            <div className="p-4">
              <Empty
                icon={<LuFileText className="h-6 w-6" />}
                title="还没有 QA 数据集"
                description="创建数据集并导入条目后，即可发起 RAG 评测"
                action={
                  canWrite ? (
                    <Button
                      size="sm"
                      icon={<LuPlus className="h-4 w-4" />}
                      onClick={() => setCreateDatasetOpen(true)}
                    >
                      新建数据集
                    </Button>
                  ) : null
                }
              />
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {datasets.map(dataset => {
                const active = dataset.id === selectedId
                return (
                  <button
                    key={dataset.id}
                    type="button"
                    onClick={() => setSelectedId(dataset.id)}
                    aria-current={active ? 'true' : undefined}
                    className={`block w-full px-3 py-3 text-left transition-colors ${
                      active ? 'bg-gray-50' : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-medium text-gray-900">
                        {dataset.name}
                      </span>
                      {sourceBadge(dataset.source_type)}
                    </div>
                    <p className="mt-1 truncate text-xs text-gray-500">
                      {dataset.description || '暂无描述'}
                    </p>
                    <p className="mt-1 text-[11px] text-gray-400">
                      更新 {formatDateTime(dataset.updated_at)}
                    </p>
                  </button>
                )
              })}
            </div>
          )}

          {listPagination && listPagination.total > PAGE_SIZE ? (
            <div className="border-t border-gray-100 p-3">
              <Pagination
                current={page}
                pageSize={PAGE_SIZE}
                total={listPagination.total}
                onChange={nextPage => {
                  setPage(Math.min(totalPages, Math.max(1, nextPage)))
                }}
              />
            </div>
          ) : null}
        </aside>

        <main className="min-w-0 border border-gray-200 bg-white">
          {!selectedId ? (
            <div className="p-6">
              <Empty title="选择一个数据集" description="左侧选择数据集后查看版本与条目" />
            </div>
          ) : detailQuery.isLoading ? (
            <PageLoading label="正在加载数据集..." />
          ) : detailQuery.isError ? (
            <div className="p-4">
              <AsyncState error={detailQuery.error} onRetry={() => detailQuery.refetch()} />
            </div>
          ) : detailQuery.data ? (
            <div className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-xl font-semibold text-gray-900">
                      {detailQuery.data.name}
                    </h2>
                    {sourceBadge(detailQuery.data.source_type)}
                  </div>
                  <p className="mt-1 text-sm text-gray-600">
                    {detailQuery.data.description || '暂无描述'}
                  </p>
                  <p className="mt-1 text-[11px] text-gray-400">
                    创建 {formatDateTime(detailQuery.data.created_at)} · 更新{' '}
                    {formatDateTime(detailQuery.data.updated_at)}
                  </p>
                </div>
                {canWrite ? (
                  <Button
                    size="sm"
                    variant="outline"
                    icon={<LuPlus className="h-4 w-4" />}
                    onClick={() => setCreateVersionOpen(true)}
                  >
                    新建版本
                  </Button>
                ) : null}
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-900">版本</h3>
                  <span className="text-xs text-gray-400">{versions.length} 个</span>
                </div>
                {versions.length === 0 ? (
                  <div className="mt-3">
                    <Empty
                      title="还没有版本"
                      description="创建草稿版本后导入条目"
                      action={
                        canWrite ? (
                          <Button
                            size="sm"
                            icon={<LuPlus className="h-4 w-4" />}
                            onClick={() => setCreateVersionOpen(true)}
                          >
                            新建草稿
                          </Button>
                        ) : null
                      }
                    />
                  </div>
                ) : (
                  <div className="mt-2 divide-y divide-gray-100 border border-gray-200">
                    {versions.map(version => {
                      const active = version.id === selectedVersionId
                      return (
                        <button
                          key={version.id}
                          type="button"
                          onClick={() => {
                            setSelectedVersionId(version.id)
                            setItemPage(1)
                          }}
                          aria-current={active ? 'true' : undefined}
                          className={`flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left ${
                            active ? 'bg-gray-50' : 'hover:bg-gray-50'
                          }`}
                        >
                          <span className="font-mono text-sm text-gray-900">
                            v{version.version}
                          </span>
                          {versionBadge(version.status)}
                          <span className="text-xs text-gray-500">{version.item_count} 条</span>
                          <span className="min-w-0 flex-1 truncate text-xs text-gray-500">
                            {version.note || '—'}
                          </span>
                          <span className="text-[11px] text-gray-400">
                            {formatDateTime(version.published_at || version.created_at)}
                          </span>
                          <LuChevronRight className="h-4 w-4 text-gray-400" aria-hidden="true" />
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>

              {selectedVersion ? (
                <div className="mt-5 border-t border-gray-200 pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-gray-900">
                        版本 v{selectedVersion.version}
                      </h3>
                      {versionBadge(selectedVersion.status)}
                      {selectedVersion.status === 'published' ? (
                        <span className="text-xs text-gray-500">已发布 · 不可变</span>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {canWrite && selectedVersion.status === 'draft' ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            icon={<LuUpload className="h-4 w-4" />}
                            onClick={() => setImportOpen(true)}
                          >
                            导入 JSON
                          </Button>
                          <Button
                            size="sm"
                            icon={<LuSend className="h-4 w-4" />}
                            disabled={selectedVersion.item_count === 0}
                            onClick={() => setPublishTarget(selectedVersion)}
                          >
                            发布版本
                          </Button>
                        </>
                      ) : null}
                      {canWrite && selectedVersion.status === 'published' ? (
                        <Button
                          size="sm"
                          icon={<LuFlaskConical className="h-4 w-4" />}
                          onClick={() =>
                            navigate(
                              `/rag-evaluations?action=create&dataset_id=${selectedId}&dataset_version_id=${selectedVersion.id}`
                            )
                          }
                        >
                          发起评测
                        </Button>
                      ) : null}
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label="刷新版本数据"
                        onClick={() => refreshSelected()}
                        icon={<LuRefreshCw className="h-4 w-4" />}
                      />
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    <div className="border border-gray-100 bg-gray-50 px-3 py-2">
                      <p className="text-[11px] text-gray-500">条目</p>
                      <p className="text-lg font-semibold text-gray-900">
                        {statsQuery.data?.item_count ?? selectedVersion.item_count}
                      </p>
                    </div>
                    <div className="border border-gray-100 bg-gray-50 px-3 py-2">
                      <p className="text-[11px] text-gray-500">Split</p>
                      <p className="font-mono text-xs text-gray-900">
                        train {statsQuery.data?.split_counts?.train ?? 0} · valid{' '}
                        {statsQuery.data?.split_counts?.valid ?? 0} · test{' '}
                        {statsQuery.data?.split_counts?.test ?? 0}
                      </p>
                    </div>
                    <div className="border border-gray-100 bg-gray-50 px-3 py-2">
                      <p className="text-[11px] text-gray-500">证据覆盖</p>
                      <p className="text-lg font-semibold text-gray-900">
                        {statsQuery.data?.evidence
                          ? percent(statsQuery.data.evidence.coverage_rate)
                          : '—'}
                      </p>
                    </div>
                  </div>

                  {statsQuery.data?.category_counts &&
                  Object.keys(statsQuery.data.category_counts).length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {Object.entries(statsQuery.data.category_counts).map(([category, count]) => (
                        <Badge key={category} size="sm" variant="default">
                          {category} {count}
                        </Badge>
                      ))}
                    </div>
                  ) : null}

                  <div className="mt-4">
                    {itemsQuery.isLoading ? (
                      <PageLoading label="正在加载条目..." />
                    ) : itemsQuery.isError ? (
                      <AsyncState error={itemsQuery.error} onRetry={() => itemsQuery.refetch()} />
                    ) : items.length === 0 ? (
                      <Empty
                        title="该版本还没有条目"
                        description={
                          selectedVersion.status === 'draft'
                            ? '导入 JSON 后即可发布版本'
                            : '已发布版本没有条目'
                        }
                        action={
                          canWrite && selectedVersion.status === 'draft' ? (
                            <Button
                              size="sm"
                              icon={<LuUpload className="h-4 w-4" />}
                              onClick={() => setImportOpen(true)}
                            >
                              导入 JSON
                            </Button>
                          ) : null
                        }
                      />
                    ) : (
                      <>
                        <Table
                          caption="数据集条目"
                          columns={itemColumns}
                          dataSource={items}
                          rowKey="id"
                          emptyText="暂无条目"
                        />
                        {itemsPagination && itemsPagination.total > ITEM_PAGE_SIZE ? (
                          <Pagination
                            className="mt-3"
                            current={itemPage}
                            pageSize={ITEM_PAGE_SIZE}
                            total={itemsPagination.total}
                            onChange={nextPage => setItemPage(Math.max(1, nextPage))}
                          />
                        ) : null}
                      </>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </main>
      </div>

      <CreateDatasetModal
        open={createDatasetOpen}
        onClose={() => setCreateDatasetOpen(false)}
        onCreated={handleDatasetCreated}
      />
      <CreateVersionModal
        open={createVersionOpen}
        onClose={() => setCreateVersionOpen(false)}
        dataset={detailQuery.data}
        versions={versions}
        onCreated={handleVersionCreated}
      />
      <ImportItemsModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        datasetId={selectedId}
        version={selectedVersion}
        onImported={handleImported}
      />
      <PublishVersionModal
        open={Boolean(publishTarget)}
        onClose={() => setPublishTarget(null)}
        datasetId={selectedId}
        version={publishTarget}
        onPublished={handlePublished}
      />
      <EditItemModal
        open={Boolean(editItem)}
        onClose={() => setEditItem(null)}
        datasetId={selectedId}
        versionId={selectedVersionId}
        item={editItem}
        onSaved={handleItemSaved}
      />
    </section>
  )
}
