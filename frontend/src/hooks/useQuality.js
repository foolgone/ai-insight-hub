import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as qualityApi from '../api/quality'
import { taskKeys } from './useTasks'

export const qualityKeys = {
  all: ['quality'],
  list: (datasourceId, params) => ['quality', datasourceId, 'list', params],
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
