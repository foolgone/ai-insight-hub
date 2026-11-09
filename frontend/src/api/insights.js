import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 转写文本的结构化摘要（内容路由产出，analysis_type='other'）。
 * @param {string} datasourceId
 * @param {{ limit?: number }} [params]
 */
export async function listTranscriptSummaries(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.analysis.summaries(datasourceId), { params })
  return data
}
