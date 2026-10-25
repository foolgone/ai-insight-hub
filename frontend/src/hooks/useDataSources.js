import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as datasourceApi from '../api/datasources'

/** 数据源 Query key（切源时只按 key 精确失效，不做全量刷新）。 */
export const dataSourceKeys = {
  all: ['datasources'],
  list: params => ['datasources', 'list', params],
  detail: id => ['datasources', 'detail', id],
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
