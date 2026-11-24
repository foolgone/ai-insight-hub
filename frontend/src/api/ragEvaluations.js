import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * RAG 批量评测（Phase 3C）与只读依赖（数据集 / Trace）。
 * 全部复用现有后端 API，不新增路由。
 */

/** @param {{ page?: number, limit?: number, status?: string, execution_mode?: string, adapter?: string, dataset_id?: string }} [params] */
export async function listRagEvaluations(params = {}) {
  const { data } = await apiClient.get(endpoints.ragEvaluations.root, { params })
  return data
}

/** @param {string} runId */
export async function getRagEvaluation(runId) {
  const { data } = await apiClient.get(endpoints.ragEvaluations.byId(runId))
  return data
}

/** @param {string} runId @param {{ page?: number, limit?: number, metric_name?: string, status?: string, dataset_item_id?: string }} [params] */
export async function listRagEvaluationResults(runId, params = {}) {
  const { data } = await apiClient.get(endpoints.ragEvaluations.results(runId), { params })
  return data
}

/** @param {string} runId @param {{ page?: number, limit?: number, metric_name?: string }} [params] */
export async function listRagEvaluationFailures(runId, params = {}) {
  const { data } = await apiClient.get(endpoints.ragEvaluations.failures(runId), { params })
  return data
}

/** @param {{ dataset_version_id: string, execution_mode: string, adapter?: string, split?: string, limit?: number, top_k?: number, judge_prompt_version?: string, judge_metrics?: string[] }} payload */
export async function createRagEvaluation(payload) {
  const { data } = await apiClient.post(endpoints.ragEvaluations.root, payload)
  return data
}

/** @param {string} runId */
export async function retryRagEvaluation(runId) {
  const { data } = await apiClient.post(endpoints.ragEvaluations.retry(runId))
  return data
}

/** @param {string} runId */
export async function cancelRagEvaluation(runId) {
  const { data } = await apiClient.post(endpoints.ragEvaluations.cancel(runId))
  return data
}

/** @param {string} traceId */
export async function getRagTrace(traceId) {
  const { data } = await apiClient.get(endpoints.rag.trace(traceId))
  return data
}

/** @param {{ page?: number, limit?: number }} [params] */
export async function listDatasets(params = {}) {
  const { data } = await apiClient.get(endpoints.qaDatasets.root, { params })
  return data
}

/** @param {string} datasetId */
export async function listDatasetVersions(datasetId) {
  const { data } = await apiClient.get(endpoints.qaDatasets.versions(datasetId))
  return data
}

/** @param {string} datasetId @param {string} versionId @param {{ page?: number, limit?: number }} [params] */
export async function listDatasetItems(datasetId, versionId, params = {}) {
  const { data } = await apiClient.get(endpoints.qaDatasets.items(datasetId, versionId), {
    params,
  })
  return data
}

/** @param {string} datasetId @param {string} versionId @param {string} itemId */
export async function getDatasetItem(datasetId, versionId, itemId) {
  const { data } = await apiClient.get(
    endpoints.qaDatasets.item(datasetId, versionId, itemId)
  )
  return data
}
