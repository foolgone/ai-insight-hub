import { useMemo, useState } from 'react'
import { LuPlus, LuRefreshCw } from 'react-icons/lu'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { DatePicker } from '../../components/DatePicker'
import { Empty } from '../../components/Empty'
import { Input } from '../../components/Input'
import { Pagination } from '../../components/Pagination'
import { Progress } from '../../components/Progress'
import { Table } from '../../components/Table'
import { Tabs } from '../../components/Tabs'
import { AgentStatusBadge } from '../../components/business/AgentStatusBadge'
import { CleanedDataDrawer } from '../../components/cleaning/CleanedDataDrawer'
import { CreateCleaningModal } from '../../components/cleaning/CreateCleaningModal'
import { useCleanedDataQuery } from '../../hooks/useCleaning'
import { useCancelTask, useRetryTask, useTasksQuery } from '../../hooks/useTasks'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { getErrorMessage } from '../../lib/errorMessages'
import { formatDateTime } from '../../lib/format'
import { notify } from '../../lib/toast'

const TASK_TABS = [
  { key: 'all', label: '全部' },
  { key: 'running', label: '进行中' },
  { key: 'completed', label: '已完成' },
  { key: 'failed', label: '失败' },
  { key: 'cancelled', label: '已取消' },
]

const TASK_TYPE_LABELS = {
  clean: '清洗',
  evaluate: '评估',
  extract: '提取',
  analyze: '洞察',
  report: '报告',
}

const TASK_PAGE_SIZE = 20
const RESULT_PAGE_SIZE = 10

function TruncatedCell({ text }) {
  return (
    <span className="block max-w-[260px] truncate" title={text}>
      {text}
    </span>
  )
}

export default function DataCleaning() {
  const currentDatasourceId = useDatasourceStore(state => state.currentId)

  const [activeStatus, setActiveStatus] = useState('all')
  const [taskPage, setTaskPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedResult, setSelectedResult] = useState(null)

  const [resultPage, setResultPage] = useState(1)
  const [minScore, setMinScore] = useState('')
  const [onlyIssues, setOnlyIssues] = useState(false)
  const [dateRange, setDateRange] = useState({ start: '', end: '' })

  const cancelMutation = useCancelTask()
  const retryMutation = useRetryTask()

  const taskParams = useMemo(
    () => ({
      task_type: 'clean',
      page: taskPage,
      limit: TASK_PAGE_SIZE,
      sort: '-created_at',
      ...(activeStatus === 'all' ? {} : { status: activeStatus }),
    }),
    [activeStatus, taskPage]
  )

  const tasksQuery = useTasksQuery(taskParams, {
    refetchInterval: query => {
      const items = query.state.data?.items || []
      const hasActive = items.some(task => task.status === 'pending' || task.status === 'running')
      return hasActive ? 3000 : false
    },
  })

  const resultParams = useMemo(
    () => ({
      page: resultPage,
      limit: RESULT_PAGE_SIZE,
      ...(minScore ? { quality_score_min: Number(minScore) } : {}),
      ...(onlyIssues ? { has_issues: true } : {}),
      ...(dateRange.start ? { date_from: dateRange.start } : {}),
      ...(dateRange.end ? { date_to: `${dateRange.end}T23:59:59` } : {}),
    }),
    [resultPage, minScore, onlyIssues, dateRange]
  )

  const cleanedQuery = useCleanedDataQuery(currentDatasourceId, resultParams)

  const handleCancel = async task => {
    try {
      await cancelMutation.mutateAsync(task.id)
      notify.success('任务已取消')
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  const handleRetry = async task => {
    try {
      await retryMutation.mutateAsync(task.id)
      notify.success('任务已重新入队')
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  const taskColumns = [
    {
      key: 'id',
      title: '任务 ID',
      render: (_, task) => <span className="font-mono text-xs">{String(task.id).slice(0, 8)}</span>,
    },
    {
      key: 'type',
      title: '类型',
      dataIndex: 'task_type',
      render: value => TASK_TYPE_LABELS[value] || value,
    },
    {
      key: 'status',
      title: '状态',
      dataIndex: 'status',
      render: value => <AgentStatusBadge status={value} />,
    },
    {
      key: 'progress',
      title: '进度',
      dataIndex: 'progress',
      render: value => <Progress percent={value || 0} showPercent />,
    },
    {
      key: 'created_at',
      title: '创建时间',
      dataIndex: 'created_at',
      render: value => formatDateTime(value),
    },
    {
      key: 'actions',
      title: '操作',
      render: (_, task) => {
        if (task.status === 'pending' || task.status === 'running') {
          return (
            <Button
              size="sm"
              variant="outline"
              loading={cancelMutation.isPending && cancelMutation.variables === task.id}
              onClick={() => handleCancel(task)}
            >
              取消
            </Button>
          )
        }
        if (task.status === 'failed') {
          return (
            <Button
              size="sm"
              variant="outline"
              loading={retryMutation.isPending && retryMutation.variables === task.id}
              onClick={() => handleRetry(task)}
            >
              重试
            </Button>
          )
        }
        if (task.status === 'completed') {
          return (
            <a href="#cleaned-results" className="text-sm text-primary-600 hover:text-primary-700">
              查看结果
            </a>
          )
        }
        return <span className="text-xs text-gray-400">—</span>
      },
    },
  ]

  const resultColumns = [
    {
      key: 'timestamp',
      title: '时间',
      dataIndex: 'timestamp',
      render: value => formatDateTime(value),
    },
    {
      key: 'user_message',
      title: '用户消息',
      dataIndex: 'user_message',
      render: value => <TruncatedCell text={value} />,
    },
    {
      key: 'ai_response',
      title: 'AI 回复',
      dataIndex: 'ai_response',
      render: value => <TruncatedCell text={value} />,
    },
    {
      key: 'quality_score',
      title: '质量分',
      dataIndex: 'quality_score',
      render: value => Number(value ?? 0).toFixed(1),
    },
    {
      key: 'issues',
      title: '问题',
      dataIndex: 'issues',
      render: issues =>
        Array.isArray(issues) && issues.length > 0 ? (
          <Badge variant="warning" size="sm">
            {issues.length}
          </Badge>
        ) : (
          '—'
        ),
    },
    {
      key: 'actions',
      title: '操作',
      render: (_, item) => (
        <Button size="sm" variant="ghost" onClick={() => setSelectedResult(item)}>
          查看
        </Button>
      ),
    },
  ]

  const tasks = tasksQuery.data?.items || []
  const taskPagination = tasksQuery.data?.pagination
  const cleanedItems = cleanedQuery.data?.items || []
  const cleanedPagination = cleanedQuery.data?.pagination

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">数据清洗</h1>
          <p className="mt-1 text-sm text-gray-500">
            清洗任务异步执行，进行中的任务每 3 秒自动刷新进度。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={<LuRefreshCw className="h-4 w-4" />}
            onClick={() => tasksQuery.refetch()}
          >
            刷新
          </Button>
          <Button icon={<LuPlus className="h-4 w-4" />} onClick={() => setCreateOpen(true)}>
            新建清洗任务
          </Button>
        </div>
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <Tabs
          items={TASK_TABS}
          value={activeStatus}
          onChange={value => {
            setActiveStatus(value)
            setTaskPage(1)
          }}
        />

        <div className="mt-4">
          <Table
            columns={taskColumns}
            dataSource={tasks}
            loading={tasksQuery.isLoading}
            emptyText={activeStatus === 'all' ? '暂无清洗任务，先新建一个吧' : '当前状态下暂无任务'}
            caption="清洗任务列表"
          />

          {tasksQuery.isError ? (
            <div className="mt-3 flex items-center justify-between rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700">
              任务列表加载失败：{getErrorMessage(tasksQuery.error)}
              <Button size="sm" variant="outline" onClick={() => tasksQuery.refetch()}>
                重试
              </Button>
            </div>
          ) : null}

          {taskPagination && taskPagination.total > 0 ? (
            <Pagination
              current={taskPage}
              pageSize={TASK_PAGE_SIZE}
              total={taskPagination.total}
              onChange={page => setTaskPage(page)}
              className="mt-3"
            />
          ) : null}
        </div>
      </div>

      <div id="cleaned-results" className="rounded-md border border-gray-200 bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">清洗结果</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              按当前数据源（Header 选择器）查询，可按质量分/问题/日期筛选。
            </p>
          </div>
          {currentDatasourceId ? (
            <Button
              variant="outline"
              icon={<LuRefreshCw className="h-4 w-4" />}
              onClick={() => cleanedQuery.refetch()}
            >
              刷新结果
            </Button>
          ) : null}
        </div>

        {!currentDatasourceId ? (
          <div className="mt-4">
            <Empty
              title="尚未选择数据源"
              description="在顶部「数据源选择器」中选择一个数据源后查看清洗结果。"
            />
          </div>
        ) : (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Input
                type="number"
                value={minScore}
                onChange={value => {
                  setMinScore(value)
                  setResultPage(1)
                }}
                placeholder="最低质量分（0–100）"
                aria-label="最低质量分"
              />
              <div className="flex items-center">
                <Checkbox
                  label="仅看有问题"
                  checked={onlyIssues}
                  onCheckedChange={checked => {
                    setOnlyIssues(checked === true)
                    setResultPage(1)
                  }}
                />
              </div>
              <div className="sm:col-span-2">
                <DatePicker
                  value={dateRange}
                  onChange={value => {
                    setDateRange(value)
                    setResultPage(1)
                  }}
                />
              </div>
            </div>

            <div className="mt-4">
              <Table
                columns={resultColumns}
                dataSource={cleanedItems}
                loading={cleanedQuery.isLoading}
                emptyText="当前筛选条件下暂无清洗结果"
                caption="清洗结果列表"
              />

              {cleanedQuery.isError ? (
                <div className="mt-3 flex items-center justify-between rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700">
                  清洗结果加载失败：{getErrorMessage(cleanedQuery.error)}
                  <Button size="sm" variant="outline" onClick={() => cleanedQuery.refetch()}>
                    重试
                  </Button>
                </div>
              ) : null}

              {cleanedPagination && cleanedPagination.total > 0 ? (
                <Pagination
                  current={resultPage}
                  pageSize={RESULT_PAGE_SIZE}
                  total={cleanedPagination.total}
                  onChange={page => setResultPage(page)}
                  className="mt-3"
                />
              ) : null}
            </div>
          </>
        )}
      </div>

      <CreateCleaningModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        defaultDatasourceId={currentDatasourceId}
      />
      <CleanedDataDrawer
        item={selectedResult}
        open={Boolean(selectedResult)}
        onClose={() => setSelectedResult(null)}
      />
    </section>
  )
}
