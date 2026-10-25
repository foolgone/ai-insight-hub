import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as reportApi from '../api/reports'
import { taskKeys } from './useTasks'

export const reportKeys = {
  all: ['reports'],
  list: (datasourceId, params) => ['reports', datasourceId, 'list', params],
  detail: reportId => ['reports', 'detail', reportId],
}

/**
 * 报告列表（生成中每 3s 轮询，完成后停止）。
 * @param {string|null|undefined} datasourceId
 * @param {Object} [params]
 * @param {Object} [options]
 */
export function useReportsQuery(datasourceId, params = {}, options = {}) {
  return useQuery({
    queryKey: reportKeys.list(datasourceId, params),
    queryFn: () => reportApi.listReports(datasourceId, params),
    enabled: Boolean(datasourceId),
    refetchInterval: query => {
      const items = query.state.data?.items || []
      const active = items.some(
        item =>
          item.status === 'pending' || item.status === 'running' || item.status === 'generating'
      )
      return active ? 3000 : false
    },
    ...options,
  })
}

/**
 * 报告详情。
 * @param {string|null|undefined} reportId
 * @param {Object} [options]
 */
export function useReportQuery(reportId, options = {}) {
  return useQuery({
    queryKey: reportKeys.detail(reportId),
    queryFn: () => reportApi.getReport(reportId),
    enabled: Boolean(reportId),
    ...options,
  })
}

/** 生成报告（202）。 */
export function useCreateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, payload }) => reportApi.createReport(datasourceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: reportKeys.all })
      queryClient.invalidateQueries({ queryKey: taskKeys.all })
    },
  })
}

/** 删除报告。 */
export function useDeleteReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: reportId => reportApi.deleteReport(reportId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reportKeys.all }),
  })
}
