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

/**
 * 拉取一个 Run 的全部结果（分页），最多 maxRows 行。
 * P1-2：对比页不能只看前 100 条；按 page/limit 拉完。
 * 限流/网关错误按 Retry-After 退避重试；仍失败由调用方展示错误与重试。
 * @param {string} runId
 * @param {{ pageSize?: number, maxRows?: number }} [options]
 */
export async function listAllRagEvaluationResults(
  runId,
  { pageSize = 100, maxRows = 1000 } = {}
) {
  const first = await fetchResultPage(runId, 1, pageSize)
  const firstItems = Array.isArray(first?.items) ? first.items : []
  const total = Number(first?.pagination?.total ?? firstItems.length)
  const totalPages = Math.min(
    Number(first?.pagination?.pages ?? Math.ceil(total / pageSize)),
    Math.ceil(maxRows / pageSize) || 1
  )
  const items = [...firstItems]
  // 串行拉页：避免一次并发过多触发限流；5-10 页的延迟可忽略。
  for (let page = 2; page <= totalPages; page += 1) {
    const payload = await fetchResultPage(runId, page, pageSize)
    if (Array.isArray(payload?.items)) items.push(...payload.items)
  }
  const capped = items.slice(0, maxRows)
  return {
    items: capped,
    total,
    loaded: capped.length,
    truncated: total > capped.length,
    totalPages,
  }
}

const RETRYABLE_STATUS = new Set([429, 502, 503, 504])

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function fetchResultPage(runId, page, pageSize) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await listRagEvaluationResults(runId, { page, limit: pageSize })
    } catch (error) {
      const status = Number(error?.status) || 0
      const retryable = status === 0 || RETRYABLE_STATUS.has(status)
      if (!retryable || attempt >= 2) throw error
      const retryAfterMs = Math.min(Number(error?.retryAfter || 0) * 1000, 10000)
      await sleep(retryAfterMs || 500 * 2 ** attempt)
    }
  }
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
  const { data } = await apiClient.get(endpoints.qaDatasets.item(datasetId, versionId, itemId))
  return data
}
