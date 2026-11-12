import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 知识库 FAQ 列表（GET /datasources/{id}/knowledge/faq）。
 * @param {string} datasourceId
 * @param {{ page?: number, limit?: number, category?: string, min_frequency?: number, sort?: string }} [params]
 */
export async function listFaq(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.knowledge.faq(datasourceId), { params })
  return data
}

/**
 * 知识检索（GET .../knowledge/search）。
 * @param {string} datasourceId
 * @param {{ q: string, limit?: number, threshold?: number }} params
 */
export async function searchKnowledge(datasourceId, params) {
  const { data } = await apiClient.get(endpoints.knowledge.search(datasourceId), { params })
  return data
}

/**
 * 知识盲区台账（GET .../knowledge/gaps）。
 * @param {string} datasourceId
 * @param {{ status?: 'open'|'adopted'|'ignored' }} [params]
 */
export async function listGaps(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.knowledge.gaps(datasourceId), { params })
  return data
}

/**
 * 更新盲区状态（PATCH .../knowledge/gaps/{gap_id}）。
 * @param {string} datasourceId
 * @param {string} gapId
 * @param {{ status: 'open'|'adopted'|'ignored', faq_id?: string }} payload
 */
export async function updateGap(datasourceId, gapId, payload) {
  const { data } = await apiClient.patch(endpoints.knowledge.gapById(datasourceId, gapId), payload)
  return data
}

/**
 * 知识覆盖率（GET .../knowledge/coverage）。
 * @param {string} datasourceId
 * @param {{ days?: number, threshold?: number }} [params]
 */
export async function getCoverage(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.knowledge.coverage(datasourceId), { params })
  return data
}

/**
 * 触发知识提取（POST .../extract-knowledge，202）。
 * @param {string} datasourceId
 * @param {{ min_frequency?: number, similarity_threshold?: number, max_faq_count?: number }} [payload]
 */
export async function extractKnowledge(datasourceId, payload = {}) {
  const { data } = await apiClient.post(endpoints.knowledge.extract(datasourceId), payload)
  return data
}

/**
 * 手动创建 FAQ（POST .../knowledge/faq）。
 * @param {string} datasourceId
 * @param {Object} payload
 */
export async function createFaq(datasourceId, payload) {
  const { data } = await apiClient.post(endpoints.knowledge.faq(datasourceId), payload)
  return data
}

/**
 * 更新 FAQ（PATCH .../faq/{faq_id}）。
 * @param {string} datasourceId
 * @param {string} faqId
 * @param {Object} payload
 */
export async function updateFaq(datasourceId, faqId, payload) {
  const { data } = await apiClient.patch(endpoints.knowledge.faqById(datasourceId, faqId), payload)
  return data
}

/**
 * 删除 FAQ（DELETE .../faq/{faq_id}）。
 * @param {string} datasourceId
 * @param {string} faqId
 */
export async function deleteFaq(datasourceId, faqId) {
  const { data } = await apiClient.delete(endpoints.knowledge.faqById(datasourceId, faqId))
  return data
}
