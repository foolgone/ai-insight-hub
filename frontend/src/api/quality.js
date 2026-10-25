import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 触发质量评估（POST .../analyze/quality，202）。
 * 请求体固定为 `{ data_ids, config: { dimensions, threshold } }`（A-9，无 include_kb）。
 * @param {string} datasourceId
 * @param {{ dataIds?: string[], dimensions?: string[], threshold?: number }} [options]
 */
export async function triggerQuality(datasourceId, { dataIds = [], dimensions, threshold } = {}) {
  const { data } = await apiClient.post(endpoints.analysis.quality(datasourceId), {
    data_ids: dataIds,
    ...(dimensions || threshold !== undefined
      ? {
          config: {
            ...(dimensions ? { dimensions } : {}),
            ...(threshold !== undefined ? { threshold } : {}),
          },
        }
      : {}),
  })
  return data
}

/**
 * 评估结果列表（GET .../analysis/quality）。
 * @param {string} datasourceId
 * @param {{ page?: number, limit?: number, sort?: string }} [params]
 */
export async function listQualityResults(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.analysis.qualityResults(datasourceId), {
    params,
  })
  return data
}

/**
 * 人工复核（POST .../analysis/quality/{result_id}/review）。
 * @param {string} datasourceId
 * @param {string} resultId
 * @param {{ decision: 'approved'|'rejected'|'corrected', note?: string, corrected_scores?: Object }} payload
 */
export async function reviewQuality(datasourceId, resultId, payload) {
  const { data } = await apiClient.post(
    endpoints.analysis.qualityReview(datasourceId, resultId),
    payload
  )
  return data
}
