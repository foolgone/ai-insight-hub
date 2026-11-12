import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as qualityApi from '../api/quality'
import { taskKeys } from './useTasks'

export const qualityKeys = {
  all: ['quality'],
  list: (datasourceId, params) => ['quality', datasourceId, 'list', params],
  runs: (datasourceId, params = {}) => ['quality', datasourceId, 'runs', params],
  compare: (datasourceId, baseRunId, targetRunId) => [
    'quality',
    datasourceId,
    'compare',
    baseRunId,
    targetRunId,
  ],
}

/**
 * 评估结果列表（按数据源；无数据源时不请求）。
 * @param {string|null|undefined} datasourceId
 * @param {Object} [params]
 * @param {Object} [options]
 */
export function useQualityResultsQuery(datasourceId, params = {}, options = {}) {
  return useQuery({
    queryKey: qualityKeys.list(datasourceId, params),
    queryFn: () => qualityApi.listQualityResults(datasourceId, params),
    enabled: Boolean(datasourceId),
    ...options,
  })
}

/**
 * 批次列表（每次评估任务一个批次；无数据源时不请求）。
 * @param {string|null|undefined} datasourceId
 * @param {Object} [options]
 */
export function useQualityRunsQuery(datasourceId, params = {}, options = {}) {
  return useQuery({
    queryKey: qualityKeys.runs(datasourceId, params),
    queryFn: () => qualityApi.listQualityRuns(datasourceId, { limit: 20, ...params }),
    enabled: Boolean(datasourceId),
    ...options,
  })
}

/**
 * 洞察批次对比（两次 completed 的 analyze 任务）。
 * @param {string|null|undefined} datasourceId
 * @param {string|null|undefined} baseRunId
 * @param {string|null|undefined} targetRunId
 */
export function useInsightRunComparisonQuery(datasourceId, baseRunId, targetRunId) {
  return useQuery({
    queryKey: ['quality', datasourceId, 'insight-compare', baseRunId, targetRunId],
    queryFn: () => qualityApi.compareInsightRuns(datasourceId, baseRunId, targetRunId),
    enabled: Boolean(datasourceId && baseRunId && targetRunId && baseRunId !== targetRunId),
  })
}

/**
 * 批次对比（两个批次都选定且不同才请求）。
 * @param {string|null|undefined} datasourceId
 * @param {string|null|undefined} baseRunId
 * @param {string|null|undefined} targetRunId
 * @param {Object} [options]
 */
export function useQualityRunComparisonQuery(datasourceId, baseRunId, targetRunId, options = {}) {
  return useQuery({
    queryKey: qualityKeys.compare(datasourceId, baseRunId, targetRunId),
    queryFn: () => qualityApi.compareQualityRuns(datasourceId, baseRunId, targetRunId),
    enabled: Boolean(datasourceId && baseRunId && targetRunId && baseRunId !== targetRunId),
    ...options,
  })
}

/** 触发评估：失效任务列表 + 当前数据源评估结果。 */
export function useTriggerQuality() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, dataIds, dimensions, threshold }) =>
      qualityApi.triggerQuality(datasourceId, { dataIds, dimensions, threshold }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: taskKeys.all })
      queryClient.invalidateQueries({ queryKey: qualityKeys.all })
      if (variables?.datasourceId) {
        queryClient.invalidateQueries({
          queryKey: qualityKeys.list(variables.datasourceId, {}),
        })
      }
    },
  })
}

/** 人工复核：成功后失效评估结果。 */
export function useReviewQuality() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, resultId, payload }) =>
      qualityApi.reviewQuality(datasourceId, resultId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qualityKeys.all }),
  })
}
