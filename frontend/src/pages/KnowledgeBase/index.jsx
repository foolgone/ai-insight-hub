import { useMemo, useState } from 'react'
import { LuDownload, LuPlus, LuSparkles } from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
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
  useGapsQuery,
  useKnowledgeSearchQuery,
} from '../../hooks/useKnowledge'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { downloadTextFile, toCsv } from '../../lib/download'
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

const TABS = [
  { key: 'faq', label: '知识条目' },
  { key: 'gaps', label: '知识盲区' },
  { key: 'search', label: '知识检索' },
]

export default function KnowledgeBase() {
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const [activeTab, setActiveTab] = useState('faq')
  const [category, setCategory] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [extractOpen, setExtractOpen] = useState(false)
  const [drawerState, setDrawerState] = useState({ open: false, faq: null, prefill: '' })

  const faqQuery = useFaqInfiniteQuery(
    currentDatasourceId,
    { limit: 10, ...(category ? { category } : {}) },
    { enabled: Boolean(currentDatasourceId) && activeTab === 'faq' }
  )
  const gapsQuery = useGapsQuery(currentDatasourceId)
  const searchQuery = useKnowledgeSearchQuery(currentDatasourceId, searchTerm, { limit: 10 })
  const deleteMutation = useDeleteFaq()

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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">知识库</h1>
          <p className="mt-1 text-sm text-gray-500">
            从清洗结果提取 FAQ、管理知识条目与盲区；知识检索返回相似度。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
        </div>
      </div>

      {!currentDatasourceId ? (
        <Empty
          title="尚未选择数据源"
          description="在顶部「数据源选择器」中选择数据源后管理知识库。"
        />
      ) : (
        <>
          <Tabs items={TABS} value={activeTab} onChange={value => setActiveTab(value)} />

          {activeTab === 'faq' ? (
            <div className="space-y-4">
              <div className="max-w-xs">
                <Select
                  options={CATEGORY_OPTIONS}
                  value={category || 'all'}
                  onChange={value => setCategory(value === 'all' ? '' : value)}
                />
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
              {gapsQuery.isLoading ? <PageLoading label="正在加载知识盲区..." /> : null}
              {gapsQuery.isError ? (
                <AsyncState error={gapsQuery.error} onRetry={() => gapsQuery.refetch()} />
              ) : null}
              {!gapsQuery.isLoading && !gapsQuery.isError ? (
                gaps.length === 0 ? (
                  <Empty title="暂无知识盲区" description="知识提取完成后展示高频未覆盖问题。" />
                ) : (
                  gaps.map(gap => {
                    const priority = PRIORITY_META[gap.priority] || PRIORITY_META.low
                    return (
                      <article
                        key={`${gap.question}-${gap.category || ''}`}
                        className="flex flex-col gap-2 rounded-md border border-gray-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-gray-900">{gap.question}</h3>
                            <Badge variant={priority.variant} size="sm">
                              {priority.label}
                            </Badge>
                            {gap.category ? (
                              <Badge variant="info" size="sm">
                                {gap.category}
                              </Badge>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-gray-500">出现 {gap.frequency ?? 0} 次</p>
                        </div>
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
