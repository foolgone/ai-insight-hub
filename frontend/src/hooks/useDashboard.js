import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, subDays } from 'date-fns'
import { useDataSourcesQuery } from './useDataSources'
import { useTasksQuery } from './useTasks'
import { useQualityResultsQuery } from './useQuality'
import { listFaq } from '../api/knowledge'
import { listReports } from '../api/reports'
import { countQualityLevels } from '../lib/quality'

const REFRESH_INTERVAL = 30000

/**
 * Dashboard 聚合数据（F-301）：4 卡 + 7 天趋势 + 质量分布（D-F21）+ 最近任务。
 * @param {string|null|undefined} datasourceId
 */
export function useDashboard(datasourceId) {
  const datasourcesQuery = useDataSourcesQuery(
    { page: 1, limit: 100, sort: '-created_at' },
    { refetchInterval: REFRESH_INTERVAL }
  )
  const tasksQuery = useTasksQuery(
    { page: 1, limit: 100, sort: '-created_at' },
    { refetchInterval: REFRESH_INTERVAL }
  )
  const qualityQuery = useQualityResultsQuery(
    datasourceId,
    { page: 1, limit: 100, sort: '-created_at' },
    { refetchInterval: REFRESH_INTERVAL }
  )
  const faqQuery = useQuery({
    queryKey: ['dashboard', 'faq', datasourceId],
    queryFn: () => listFaq(datasourceId, { page: 1, limit: 1 }),
    enabled: Boolean(datasourceId),
    refetchInterval: REFRESH_INTERVAL,
  })
  const reportsQuery = useQuery({
    queryKey: ['dashboard', 'reports', datasourceId],
    queryFn: () => listReports(datasourceId, { page: 1, limit: 1 }),
    enabled: Boolean(datasourceId),
    refetchInterval: REFRESH_INTERVAL,
  })

  const stats = useMemo(
    () => [
      {
        key: 'datasources',
        label: '数据源',
        value:
          datasourcesQuery.data?.pagination?.total ?? datasourcesQuery.data?.items?.length ?? 0,
      },
      {
        key: 'tasks',
        label: '清洗任务',
        value: tasksQuery.data?.pagination?.total ?? tasksQuery.data?.items?.length ?? 0,
      },
      { key: 'knowledge', label: '知识条目', value: faqQuery.data?.pagination?.total ?? 0 },
      { key: 'reports', label: '报告数', value: reportsQuery.data?.pagination?.total ?? 0 },
    ],
    [datasourcesQuery.data, tasksQuery.data, faqQuery.data, reportsQuery.data]
  )

  const qualityDistribution = useMemo(
    () => countQualityLevels(qualityQuery.data?.items || []),
    [qualityQuery.data]
  )

  const trendData = useMemo(() => {
    const items = tasksQuery.data?.items || []
    return Array.from({ length: 7 }).map((_, index) => {
      const day = subDays(new Date(), 6 - index)
      const dateKey = format(day, 'yyyy-MM-dd')
      const value = items.filter(
        item => String(item.created_at || '').slice(0, 10) === dateKey
      ).length
      return { name: format(day, 'MM-dd'), value }
    })
  }, [tasksQuery.data])

  const recentTasks = useMemo(() => (tasksQuery.data?.items || []).slice(0, 5), [tasksQuery.data])

  const errors = [
    datasourcesQuery.error,
    tasksQuery.error,
    qualityQuery.error,
    faqQuery.error,
    reportsQuery.error,
  ].filter(Boolean)

  const isLoading =
    datasourcesQuery.isLoading ||
    tasksQuery.isLoading ||
    (Boolean(datasourceId) &&
      (qualityQuery.isLoading || faqQuery.isLoading || reportsQuery.isLoading))

  const refetch = () =>
    Promise.all([
      datasourcesQuery.refetch(),
      tasksQuery.refetch(),
      qualityQuery.refetch(),
      faqQuery.refetch(),
      reportsQuery.refetch(),
    ])

  return {
    stats,
    qualityDistribution,
    trendData,
    recentTasks,
    isLoading,
    error: errors[0] || null,
    refetch,
    hasDatasource: Boolean(datasourceId),
  }
}
