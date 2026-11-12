import { useMemo, useState } from 'react'
import { LuDownload, LuPlus, LuSparkles } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { PageHeader } from '../../components/common/PageHeader'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Empty } from '../../components/Empty'
import { Input } from '../../components/Input'
import { Select } from '../../components/Select'
import { Tabs } from '../../components/Tabs'
import { KnowledgeEntryCard } from '../../components/business/KnowledgeEntryCard'
import { FaqDrawer } from '../../components/knowledge/FaqDrawer'
import { ExtractKnowledgeModal } from '../../components/knowledge/ExtractKnowledgeModal'
import {
  useDeleteFaq,
  useFaqInfiniteQuery,
  useCoverageQuery,
  useGapsQuery,
  useKnowledgeSearchQuery,
  useUpdateFaq,
  useUpdateGap,
} from '../../hooks/useKnowledge'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { downloadTextFile, toCsv } from '../../lib/download'
import { formatDateTime } from '../../lib/format'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const CATEGORY_OPTIONS = [
  { label: '全部分类', value: 'all' },
  { label: '产品', value: '产品' },
  { label: '售后', value: '售后' },
  { label: '咨询', value: '咨询' },
  { label: '支付', value: '支付' },
  { label: '物流', value: '物流' },
  { label: '其他', value: '其他' },
]

const PRIORITY_META = {
  high: { label: '高优先级', variant: 'error' },
  medium: { label: '中优先级', variant: 'warning' },
  low: { label: '低优先级', variant: 'default' },
}

const STATUS_OPTIONS = [
  { label: '全部状态', value: 'all' },
  { label: '待审核', value: 'needs_review' },
  { label: '已启用', value: 'active' },
  { label: '已归档', value: 'archived' },
]

const TABS = [
  { key: 'faq', label: '知识条目' },
  { key: 'gaps', label: '知识盲区' },
  { key: 'search', label: '知识检索' },
]

const GAP_STATUS_OPTIONS = [
  { label: '待处理', value: 'open' },
  { label: '已采纳', value: 'adopted' },
  { label: '已忽略', value: 'ignored' },
  { label: '全部', value: 'all' },
]

const GAP_STATUS_META = {
  open: { label: '待处理', variant: 'warning' },
  adopted: { label: '已采纳', variant: 'success' },
  ignored: { label: '已忽略', variant: 'default' },
}

/** 知识覆盖率（近 7 天对话能被现有 FAQ 语义命中的比例）。 */
function CoverageStrip({ query }) {
  if (query.isLoading) {
    return <p className="text-sm text-gray-500">正在计算知识覆盖率...</p>
  }
  if (query.isError) {
    return (
      <p role="alert" className="text-sm text-error-600">
        覆盖率暂时算不出来（{getErrorMessage(query.error)}）；不影响其他功能。
      </p>
    )
  }
  const data = query.data
  if (!data) return null
  const percent = Math.round((data.rate || 0) * 1000) / 10
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-md border border-gray-200 bg-white px-4 py-3">
      <div>
        <p className="text-xs text-gray-600">知识覆盖率（近 {data.days} 天）</p>
        <p className="mt-1 text-2xl font-bold text-gray-900">{percent}%</p>
      </div>
      <p className="text-sm text-gray-600">
        {data.covered} / {data.total} 条对话能被现有 FAQ 命中
        <span className="ml-1 text-xs text-gray-500">
          （top-1 相似度 ≥ {Math.round(data.threshold * 100)}%）
        </span>
      </p>
      <p className="text-xs text-gray-500">
        {data.method === 'trgm' ? '（按文本相似度估算；向量索引未就绪时自动降级） ' : ''}
        {data.total === 0
          ? '近 7 天没有可评估的对话'
          : percent >= 80
            ? '覆盖良好，继续按盲区补知识即可'
            : '覆盖率偏低：优先处理下方「知识盲区」'}
      </p>
    </div>
  )
}

export default function KnowledgeBase() {
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const [activeTab, setActiveTab] = useState('faq')
  const [category, setCategory] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [gapStatus, setGapStatus] = useState('open')
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [extractOpen, setExtractOpen] = useState(false)
  const [drawerState, setDrawerState] = useState({ open: false, faq: null, prefill: '' })

  const faqQuery = useFaqInfiniteQuery(
    currentDatasourceId,
    {
      limit: 10,
      ...(category ? { category } : {}),
      ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
    },
    { enabled: Boolean(currentDatasourceId) && activeTab === 'faq' }
  )
  const gapsQuery = useGapsQuery(currentDatasourceId, {
    ...(gapStatus === 'all' ? {} : { status: gapStatus }),
  })
  const coverageQuery = useCoverageQuery(currentDatasourceId, { days: 7, threshold: 0.8 })
  const updateGapMutation = useUpdateGap()
  const searchQuery = useKnowledgeSearchQuery(currentDatasourceId, searchTerm, { limit: 10 })
  const deleteMutation = useDeleteFaq()
  const updateMutation = useUpdateFaq()

  const faqItems = useMemo(
    () => (faqQuery.data?.pages || []).flatMap(page => page.items || []),
    [faqQuery.data]
  )
  const gaps = gapsQuery.data?.gaps || []
  const searchResults = searchQuery.data?.results || []

  const closeDrawer = () => setDrawerState({ open: false, faq: null, prefill: '' })

  const handleDelete = async faq => {
    try {
      await deleteMutation.mutateAsync({ datasourceId: currentDatasourceId, faqId: faq.id })
      notify.success('知识条目已删除')
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  const handleApprove = async faq => {
    try {
      await updateMutation.mutateAsync({
        datasourceId: currentDatasourceId,
        faqId: faq.id,
        payload: { status: 'active' },
      })
      notify.success('知识条目已审核通过')
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  const handleGapStatus = async (gap, status) => {
    if (!gap.id) {
      notify.error('该盲区缺少 id（历史数据），请重新提取知识后再试')
      return
    }
    try {
      await updateGapMutation.mutateAsync({
        datasourceId: currentDatasourceId,
        gapId: gap.id,
        status,
      })
      notify.success(
        status === 'adopted'
          ? '已标记为已采纳'
          : status === 'ignored'
            ? '已忽略该盲区'
            : '已恢复为待处理'
      )
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  const handleExport = () => {
    const rows = [
      ['问题', '答案', '分类', '标签', '置信度', '质量分', '频次', '来源'],
      ...faqItems.map(item => [
        item.question,
        item.answer,
        item.category || '',
        (item.tags || []).join('|'),
        item.confidence ?? '',
        item.quality_score ?? '',
        item.frequency ?? '',
        item.source || '',
      ]),
    ]
    downloadTextFile(`knowledge-faq-${Date.now()}.csv`, toCsv(rows))
  }

  return (
    <section className="space-y-6">
      <PageHeader
        index="05"
        eyebrow="Knowledge"
        title="知识库"
        description="从清洗结果提取 FAQ、管理知识条目与盲区；知识检索返回相似度。"
        actions={
          <>
            <Button
              variant="outline"
              icon={<LuSparkles className="h-4 w-4" />}
              onClick={() => setExtractOpen(true)}
              disabled={!currentDatasourceId}
            >
              提取知识
            </Button>
            <Button
              variant="outline"
              icon={<LuDownload className="h-4 w-4" />}
              onClick={handleExport}
              disabled={!currentDatasourceId || faqItems.length === 0}
            >
              导出 CSV
            </Button>
            <Button
              icon={<LuPlus className="h-4 w-4" />}
              onClick={() => setDrawerState({ open: true, faq: null, prefill: '' })}
              disabled={!currentDatasourceId}
            >
              新建条目
            </Button>
          </>
        }
      />

      {!currentDatasourceId ? (
        <Empty
          title="尚未选择数据源"
          description="在顶部「数据源选择器」中选择数据源后管理知识库。"
        />
      ) : (
        <>
          <CoverageStrip query={coverageQuery} />

          <Tabs items={TABS} value={activeTab} onChange={value => setActiveTab(value)} />

          {activeTab === 'faq' ? (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <div className="w-40">
                  <Select
                    ariaLabel="知识分类筛选"
                    options={CATEGORY_OPTIONS}
                    value={category || 'all'}
                    onChange={value => setCategory(value === 'all' ? '' : value)}
                  />
                </div>
                <div className="w-36">
                  <Select
                    ariaLabel="知识状态筛选"
                    options={STATUS_OPTIONS}
                    value={statusFilter}
                    onChange={setStatusFilter}
                  />
                </div>
              </div>

              {faqQuery.isLoading ? <PageLoading label="正在加载知识条目..." /> : null}
              {faqQuery.isError ? (
                <AsyncState error={faqQuery.error} onRetry={() => faqQuery.refetch()} />
              ) : null}

              {!faqQuery.isLoading && !faqQuery.isError ? (
                faqItems.length === 0 ? (
                  <Empty
                    title="暂无知识条目"
                    description="点击「提取知识」从清洗结果生成 FAQ，或手动新建。"
                  />
                ) : (
                  <div className="space-y-3">
                    {faqItems.map(faq => (
                      <KnowledgeEntryCard
                        key={faq.id}
                        entry={faq}
                        onEdit={() => setDrawerState({ open: true, faq, prefill: '' })}
                        onDelete={() => handleDelete(faq)}
                        onApprove={() => handleApprove(faq)}
                      />
                    ))}
                    {faqQuery.hasNextPage ? (
                      <div className="flex justify-center">
                        <Button
                          variant="outline"
                          loading={faqQuery.isFetchingNextPage}
                          onClick={() => faqQuery.fetchNextPage()}
                        >
                          加载更多
                        </Button>
                      </div>
                    ) : null}
                  </div>
                )
              ) : null}
            </div>
          ) : null}

          {activeTab === 'gaps' ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <div className="w-40">
                  <Select
                    ariaLabel="盲区状态筛选"
                    options={GAP_STATUS_OPTIONS}
                    value={gapStatus}
                    onChange={setGapStatus}
                  />
                </div>
                {gapsQuery.data?.summary ? (
                  <p className="text-xs text-gray-500">
                    待处理 {gapsQuery.data.summary.open_gaps ?? 0} · 已采纳{' '}
                    {gapsQuery.data.summary.adopted_gaps ?? 0} · 已忽略{' '}
                    {gapsQuery.data.summary.ignored_gaps ?? 0}
                  </p>
                ) : null}
              </div>

              {gapsQuery.isLoading ? <PageLoading label="正在加载知识盲区..." /> : null}
              {gapsQuery.isError ? (
                <AsyncState error={gapsQuery.error} onRetry={() => gapsQuery.refetch()} />
              ) : null}
              {!gapsQuery.isLoading && !gapsQuery.isError ? (
                gaps.length === 0 ? (
                  <Empty
                    title="暂无知识盲区"
                    description={
                      gapStatus === 'open'
                        ? '当前没有待处理的盲区；可切换状态查看历史。'
                        : '该状态下没有盲区。'
                    }
                  />
                ) : (
                  gaps.map(gap => {
                    const priority = PRIORITY_META[gap.priority] || PRIORITY_META.low
                    const statusMeta = GAP_STATUS_META[gap.status] || GAP_STATUS_META.open
                    return (
                      <article
                        key={gap.id || gap.question}
                        className="flex flex-col gap-2 rounded-md border border-gray-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-gray-900">{gap.question}</h3>
                            <Badge variant={priority.variant} size="sm">
                              {priority.label}
                            </Badge>
                            <Badge variant={statusMeta.variant} size="sm">
                              {statusMeta.label}
                            </Badge>
                          </div>
                          <p className="mt-1 text-xs text-gray-500">
                            累计出现 {gap.frequency ?? 0} 次
                            {gap.last_seen ? ` · 最近 ${formatDateTime(gap.last_seen)}` : ''}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setDrawerState({
                                open: true,
                                faq: null,
                                prefill: gap.question,
                              })
                            }
                          >
                            转为 FAQ
                          </Button>
                          {gap.status !== 'adopted' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              loading={
                                updateGapMutation.isPending &&
                                updateGapMutation.variables?.gapId === gap.id
                              }
                              onClick={() => handleGapStatus(gap, 'adopted')}
                            >
                              标为已采纳
                            </Button>
                          ) : null}
                          {gap.status !== 'ignored' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleGapStatus(gap, 'ignored')}
                            >
                              忽略
                            </Button>
                          ) : null}
                          {gap.status !== 'open' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleGapStatus(gap, 'open')}
                            >
                              恢复待处理
                            </Button>
                          ) : null}
                        </div>
                      </article>
                    )
                  })
                )
              ) : null}
            </div>
          ) : null}

          {activeTab === 'search' ? (
            <div className="space-y-4">
              <form
                className="flex max-w-xl items-center gap-2"
                onSubmit={event => {
                  event.preventDefault()
                  setSearchTerm(searchInput.trim())
                }}
              >
                <Input
                  value={searchInput}
                  onChange={setSearchInput}
                  placeholder="输入关键词，如：退款"
                  aria-label="知识检索关键词"
                />
                <Button type="submit" disabled={!searchInput.trim()}>
                  搜索
                </Button>
              </form>

              {searchQuery.isLoading ? <PageLoading label="正在检索..." /> : null}
              {searchQuery.isError ? (
                <AsyncState error={searchQuery.error} onRetry={() => searchQuery.refetch()} />
              ) : null}
              {!searchQuery.isLoading && !searchQuery.isError ? (
                searchTerm && searchResults.length === 0 ? (
                  <Empty title="未检索到结果" description="尝试更换关键词或降低相似度阈值。" />
                ) : searchResults.length === 0 ? (
                  <Empty
                    title="输入关键词开始检索"
                    description="检索基于 pg_trgm + 向量混合排序。"
                  />
                ) : (
                  <div className="space-y-3">
                    {searchResults.map(item => (
                      <KnowledgeEntryCard
                        key={item.id}
                        entry={item}
                        canWrite={false}
                        searchSimilarity={item.similarity}
                      />
                    ))}
                  </div>
                )
              ) : null}
            </div>
          ) : null}
        </>
      )}

      <FaqDrawer
        open={drawerState.open}
        onClose={closeDrawer}
        datasourceId={currentDatasourceId}
        faq={drawerState.faq}
        prefillQuestion={drawerState.prefill}
      />
      <ExtractKnowledgeModal
        open={extractOpen}
        onClose={() => setExtractOpen(false)}
        datasourceId={currentDatasourceId}
      />
    </section>
  )
}
