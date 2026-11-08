import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as datasourceTypeApi from '../api/datasourceTypes'
import { getDatasourceTypeLabel } from '../lib/datasourceMeta'

export const datasourceTypeKeys = {
  all: ['datasource-types'],
  list: includeInactive => ['datasource-types', 'list', { includeInactive }],
}

/** 类型列表查询（字典表很小，缓存 1 分钟）。 */
export function useDatasourceTypesQuery({ includeInactive = false, enabled = true } = {}) {
  return useQuery({
    queryKey: datasourceTypeKeys.list(includeInactive),
    queryFn: () => datasourceTypeApi.listDatasourceTypes({ includeInactive }),
    enabled,
    staleTime: 60_000,
  })
}

/**
 * 下拉选项 + code → 展示名。
 * 后端不可用时回退到内置静态表，保证列表页仍能显示中文。
 */
export function useDatasourceTypeOptions({ includeInactive = false } = {}) {
  const query = useDatasourceTypesQuery({ includeInactive })
  const items = query.data?.items ?? []
  const options = items.map(item => ({ label: item.label, value: item.code }))
  const labelOf = code => items.find(item => item.code === code)?.label || getDatasourceTypeLabel(code)

  return { ...query, items, options, labelOf }
}

function useInvalidateTypes() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: datasourceTypeKeys.all })
}

export function useCreateDatasourceType() {
  const invalidate = useInvalidateTypes()
  return useMutation({
    mutationFn: datasourceTypeApi.createDatasourceType,
    onSuccess: invalidate,
  })
}

export function useUpdateDatasourceType() {
  const invalidate = useInvalidateTypes()
  return useMutation({
    mutationFn: ({ id, payload }) => datasourceTypeApi.updateDatasourceType(id, payload),
    onSuccess: invalidate,
  })
}

export function useDeleteDatasourceType() {
  const invalidate = useInvalidateTypes()
  return useMutation({
    mutationFn: datasourceTypeApi.deleteDatasourceType,
    onSuccess: invalidate,
  })
}
