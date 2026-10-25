import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 任务列表（GET /tasks）。
 * @param {{ page?: number, limit?: number, task_type?: string, status?: string, datasource_id?: string, sort?: string }} [params]
 * @returns {Promise<{ items: Object[], pagination: Object }>}
 */
export async function listTasks(params = {}) {
  const { data } = await apiClient.get(endpoints.tasks.list, { params })
  return data
}

/**
 * 任务详情（GET /tasks/{id}）。
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function getTask(id) {
  const { data } = await apiClient.get(endpoints.tasks.byId(id))
  return data
}

/**
 * 取消任务（POST /tasks/{id}/cancel）。
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function cancelTask(id) {
  const { data } = await apiClient.post(endpoints.tasks.cancel(id))
  return data
}

/**
 * 重试失败任务（POST /tasks/{id}/retry，202）。
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function retryTask(id) {
  const { data } = await apiClient.post(endpoints.tasks.retry(id))
  return data
}
