import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 数据源列表（GET /datasources）。
 * @param {{ page?: number, limit?: number, status?: string, type?: string, sort?: string }} [params]
 * @returns {Promise<{ items: Object[], pagination: Object }>}
 */
export async function listDataSources(params = {}) {
  const { data } = await apiClient.get(endpoints.datasources.root, { params })
  return data
}

/**
 * 数据源详情（GET /datasources/{id}）。
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function getDataSource(id) {
  const { data } = await apiClient.get(endpoints.datasources.byId(id))
  return data
}

/**
 * 创建数据源（POST /datasources，201）。
 * @param {{ name: string, description?: string, type: string, config?: Object }} payload
 * @returns {Promise<Object>}
 */
export async function createDataSource(payload) {
  const { data } = await apiClient.post(endpoints.datasources.root, payload)
  return data
}

/**
 * 更新数据源（PATCH /datasources/{id}，局部更新）。
 * @param {string} id
 * @param {Object} payload
 * @returns {Promise<Object>}
 */
export async function updateDataSource(id, payload) {
  const { data } = await apiClient.patch(endpoints.datasources.byId(id), payload)
  return data
}

/**
 * 删除数据源（DELETE /datasources/{id}，默认软删，force=true 物理删除）。
 * @param {string} id
 * @param {{ force?: boolean }} [options]
 * @returns {Promise<{ message: string, deleted_records: number }>}
 */
export async function deleteDataSource(id, { force = false } = {}) {
  const { data } = await apiClient.delete(endpoints.datasources.byId(id), {
    params: force ? { force: true } : undefined,
  })
  return data
}

/**
 * 上传数据文件（POST /datasources/{id}/upload，202）。
 * @param {string} id
 * @param {File} file CSV/JSON/XLSX/TXT，≤50MB
 * @returns {Promise<{ task_id: string, status: string, message: string, file_info: Object }>}
 */
export async function uploadDataSourceFile(id, file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post(endpoints.datasources.upload(id), formData)
  return data
}
