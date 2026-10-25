import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as cleaningApi from '../api/cleaning'
import { taskKeys } from './useTasks'

/** 清洗结果 Query key。 */
export const cleanedDataKeys = {
  all: ['cleaned-data'],
  list: (datasourceId, params) => ['cleaned-data', datasourceId, 'list', params],
  detail: (datasourceId, dataId) => ['cleaned-data', datasourceId, 'detail', dataId],
}

/**
 * 清洗结果列表查询（按当前数据源；无数据源时不请求）。
 * @param {string|null|undefined} datasourceId
 * @param {Object} [params]
 * @param {Object} [options]
 */
export function useCleanedDataQuery(datasourceId, params = {}, options = {}) {
  return useQuery({
    queryKey: cleanedDataKeys.list(datasourceId, params),
    queryFn: () => cleaningApi.listCleanedData(datasourceId, params),
    enabled: Boolean(datasourceId),
    ...options,
  })
}

/**
 * 清洗结果详情查询。
 * @param {string|null|undefined} datasourceId
 * @param {string|null|undefined} dataId
 * @param {Object} [options]
 */
export function useCleanedDataDetailQuery(datasourceId, dataId, options = {}) {
  return useQuery({
    queryKey: cleanedDataKeys.detail(datasourceId, dataId),
    queryFn: () => cleaningApi.getCleanedData(datasourceId, dataId),
    enabled: Boolean(datasourceId && dataId),
    ...options,
  })
}

/** 触发清洗并失效任务列表。 */
export function useStartCleaning() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, dataIds, config }) =>
      cleaningApi.startCleaning(datasourceId, { dataIds, config }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: taskKeys.all }),
  })
}
