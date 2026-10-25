import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 触发数据清洗（POST /datasources/{id}/clean，202）。
 * @param {string} datasourceId
 * @param {{ dataIds?: string[], config?: { remove_duplicates?: boolean, normalize_text?: boolean } }} [options]
 * @returns {Promise<{ task_id: string, estimated_duration: number, message: string }>}
 */
export async function startCleaning(datasourceId, { dataIds = [], config } = {}) {
  const { data } = await apiClient.post(endpoints.datasources.clean(datasourceId), {
    data_ids: dataIds,
    ...(config ? { config } : {}),
  })
  return data
}

/**
 * 清洗结果列表（GET /datasources/{id}/cleaned-data）。
 * @param {string} datasourceId
 * @param {Object} [params] page/limit/quality_score_min/quality_score_max/has_issues/date_from/date_to
 * @returns {Promise<{ items: Object[], pagination: Object }>}
 */
export async function listCleanedData(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.datasources.cleanedData(datasourceId), {
    params,
  })
  return data
}

/**
 * 清洗结果详情（GET /datasources/{id}/cleaned-data/{data_id}）。
 * 注意：列表项不含 id，详情仅能由其他来源拿到 data_id 时使用。
 * @param {string} datasourceId
 * @param {string} dataId
 * @returns {Promise<Object>}
 */
export async function getCleanedData(datasourceId, dataId) {
  const { data } = await apiClient.get(endpoints.datasources.cleanedDataById(datasourceId, dataId))
  return data
}
