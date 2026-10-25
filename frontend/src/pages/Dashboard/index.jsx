import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import {
  LuBookOpen,
  LuDatabase,
  LuDownload,
  LuFileText,
  LuRefreshCw,
  LuWand2,
} from 'react-icons/lu'
import { AsyncState } from '../../components/common/AsyncState'
import { PageLoading } from '../../components/common/PageLoading'
import { Button } from '../../components/Button'
import { Chart } from '../../components/Chart'
import { Empty } from '../../components/Empty'
import { StatCard } from '../../components/StatCard'
import { Table } from '../../components/Table'
import { AgentStatusBadge } from '../../components/business/AgentStatusBadge'
import { useDashboard } from '../../hooks/useDashboard'
import { useDatasourceStore } from '../../stores/datasourceStore'
import { downloadTextFile, toCsv } from '../../lib/download'
import { formatDateTime } from '../../lib/format'

const STAT_ICONS = {
  datasources: <LuDatabase className="h-5 w-5" />,
  tasks: <LuWand2 className="h-5 w-5" />,
  knowledge: <LuBookOpen className="h-5 w-5" />,
  reports: <LuFileText className="h-5 w-5" />,
}

const STAT_COLORS = {
  datasources: 'primary',
  tasks: 'info',
  knowledge: 'success',
  reports: 'warning',
}

const TASK_TYPE_LABELS = {
  clean: '清洗',
  evaluate: '评估',
  extract: '提取',
  analyze: '洞察',
  report: '报告',
}

const TASK_COLUMNS = [
  {
    key: 'id',
    title: '任务 ID',
    render: (_, task) => <span className="font-mono text-xs">{String(task.id).slice(0, 8)}</span>,
  },
  {
    key: 'task_type',
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
    key: 'created_at',
    title: '创建时间',
    dataIndex: 'created_at',
    render: value => formatDateTime(value),
  },
]

export default function Dashboard() {
  const currentDatasourceId = useDatasourceStore(state => state.currentId)
  const { stats, qualityDistribution, trendData, recentTasks, isLoading, error, refetch } =
    useDashboard(currentDatasourceId)

  const handleExport = () => {
    const rows = [
      ['指标', '数值'],
      ...stats.map(stat => [stat.label, stat.value]),
      [],
      ['最近 7 天', '任务数'],
      ...trendData.map(item => [item.name, item.value]),
    ]
    downloadTextFile(`dashboard-${format(new Date(), 'yyyyMMdd')}.csv`, toCsv(rows))
  }

  if (error) {
    return <AsyncState error={error} onRetry={refetch} />
  }

  if (isLoading) {
    return <PageLoading label="正在加载 Dashboard..." />
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 lg:text-3xl">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            数据源、清洗、知识库与报告的概览，每 30 秒自动刷新。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            icon={<LuRefreshCw className="h-4 w-4" />}
            onClick={() => refetch()}
          >
            刷新
          </Button>
          <Button
            variant="outline"
            icon={<LuDownload className="h-4 w-4" />}
            onClick={handleExport}
          >
            导出
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(stat => (
          <StatCard
            key={stat.key}
            title={stat.label}
            value={stat.value}
            icon={STAT_ICONS[stat.key]}
            color={STAT_COLORS[stat.key]}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Chart title="处理量趋势（最近 7 天）" type="line" data={trendData} height={320} />
        {currentDatasourceId ? (
          <Chart
            title="质量分布（最近 100 条样本）"
            type="pie"
            data={qualityDistribution}
            height={320}
          />
        ) : (
          <div className="rounded-md border border-gray-200 bg-white p-4">
            <h3 className="text-lg font-semibold text-gray-900">质量分布</h3>
            <div className="mt-3">
              <Empty
                title="尚未选择数据源"
                description="在顶部「数据源选择器」中选择数据源后展示质量分布。"
              />
            </div>
          </div>
        )}
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-gray-900">最近任务</h2>
          <Link to="/data-cleaning" className="text-sm text-primary-600 hover:text-primary-700">
            查看全部
          </Link>
        </div>
        <Table
          columns={TASK_COLUMNS}
          dataSource={recentTasks}
          emptyText="暂无任务"
          caption="最近任务"
        />
      </div>
    </section>
  )
}
