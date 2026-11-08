import { apiClient } from './client'
import { endpoints } from './endpoints'

/** 类型列表（含使用量）；includeInactive 用于管理页展示已停用项。 */
export async function listDatasourceTypes({ includeInactive = false } = {}) {
  const { data } = await apiClient.get(endpoints.datasourceTypes.root, {
    params: includeInactive ? { include_inactive: true } : undefined,
  })
  return data
}

/** 新增类型（admin）。code 留空则由服务端生成。 */
export async function createDatasourceType({ label, code, description, sortOrder }) {
  const { data } = await apiClient.post(endpoints.datasourceTypes.root, {
    label,
    ...(code ? { code } : {}),
    ...(description ? { description } : {}),
    ...(sortOrder === undefined || sortOrder === null ? {} : { sort_order: sortOrder }),
  })
  return data
}

/** 修改类型（admin）：名称/描述/排序/启停；code 不可改。 */
export async function updateDatasourceType(id, payload) {
  const { data } = await apiClient.patch(endpoints.datasourceTypes.byId(id), payload)
  return data
}

/** 删除类型（admin）：内置类型与使用中类型会被服务端拒绝。 */
export async function deleteDatasourceType(id) {
  await apiClient.delete(endpoints.datasourceTypes.byId(id))
}
