import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as datasourceApi from '../api/datasources'
import { cleanedDataKeys } from './useCleaning'
import { taskKeys } from './useTasks'

/** 数据源 Query key（切源时只按 key 精确失效，不做全量刷新）。 */
export const dataSourceKeys = {
  all: ['datasources'],
  list: params => ['datasources', 'list', params],
  detail: id => ['datasources', 'detail', id],
  rawData: id => ['datasources', id, 'raw-data'],
}

/**
 * 数据源列表查询。
 * @param {Object} [params]
 * @param {Object} [options]
 */
export function useDataSourcesQuery(params = {}, options = {}) {
  return useQuery({
    queryKey: dataSourceKeys.list(params),
    queryFn: () => datasourceApi.listDataSources(params),
    ...options,
  })
}

/**
 * 数据源详情查询（无 id 时不请求）。
 * @param {string|null|undefined} id
 * @param {Object} [options]
 */
export function useDataSourceQuery(id, options = {}) {
  return useQuery({
    queryKey: dataSourceKeys.detail(id),
    queryFn: () => datasourceApi.getDataSource(id),
    enabled: Boolean(id),
    ...options,
  })
}

/** 创建数据源并失效列表。 */
export function useCreateDataSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: datasourceApi.createDataSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dataSourceKeys.all }),
  })
}

/** 更新数据源并失效列表/详情。 */
export function useUpdateDataSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }) => datasourceApi.updateDataSource(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dataSourceKeys.all }),
  })
}

/** 删除数据源并失效列表。 */
export function useDeleteDataSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, force }) => datasourceApi.deleteDataSource(id, { force }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dataSourceKeys.all }),
  })
}

/** 上传数据文件并失效数据源列表（统计数据会变化）。 */
export function useUploadDataSourceFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, file }) => datasourceApi.uploadDataSourceFile(id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dataSourceKeys.all }),
  })
}

/**
 * 上传文件列表（转写 / 切分状态）；无数据源时不请求。
 * @param {string|null|undefined} datasourceId
 * @param {Object} [options]
 */
export function useRawDataQuery(datasourceId, options = {}) {
  return useQuery({
    queryKey: dataSourceKeys.rawData(datasourceId),
    queryFn: () => datasourceApi.listRawData(datasourceId),
    enabled: Boolean(datasourceId),
    ...options,
  })
}

/** 重新切分：失效文件列表、清洗结果与任务列表。 */
export function useStructureRawData() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, rawId }) => datasourceApi.structureRawData(datasourceId, rawId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: dataSourceKeys.all })
      queryClient.invalidateQueries({ queryKey: cleanedDataKeys.all })
      queryClient.invalidateQueries({ queryKey: taskKeys.all })
      if (variables?.datasourceId) {
        queryClient.invalidateQueries({
          queryKey: dataSourceKeys.rawData(variables.datasourceId),
        })
      }
    },
  })
}
