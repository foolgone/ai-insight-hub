import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * QA 数据集 API（P0-A）。
 * 路由全部复用已有 `/qa-datasets` 后端接口，不新增后端契约。
 */

export async function listQaDatasets(params = {}) {
  const { data } = await apiClient.get(endpoints.qaDatasets.root, { params })
  return data
}

export async function getQaDataset(datasetId) {
  const { data } = await apiClient.get(endpoints.qaDatasets.byId(datasetId))
  return data
}

export async function createQaDataset(payload) {
  const { data } = await apiClient.post(endpoints.qaDatasets.root, payload)
  return data
}

export async function createQaDatasetVersion(datasetId, payload = {}) {
  const { data } = await apiClient.post(endpoints.qaDatasets.versions(datasetId), payload)
  return data
}

export async function importQaDatasetItems(datasetId, versionId, items) {
  const { data } = await apiClient.post(endpoints.qaDatasets.importItems(datasetId, versionId), {
    items,
  })
  return data
}

export async function publishQaDatasetVersion(datasetId, versionId) {
  const { data } = await apiClient.post(endpoints.qaDatasets.publish(datasetId, versionId))
  return data
}

export async function listQaDatasetItems(datasetId, versionId, params = {}) {
  const { data } = await apiClient.get(endpoints.qaDatasets.items(datasetId, versionId), {
    params,
  })
  return data
}

export async function updateQaDatasetItem(datasetId, versionId, itemId, payload) {
  const { data } = await apiClient.patch(
    endpoints.qaDatasets.item(datasetId, versionId, itemId),
    payload
  )
  return data
}

export async function deleteQaDatasetItem(datasetId, versionId, itemId) {
  await apiClient.delete(endpoints.qaDatasets.item(datasetId, versionId, itemId))
}

export async function getQaDatasetStats(datasetId, versionId) {
  const { data } = await apiClient.get(endpoints.qaDatasets.stats(datasetId), {
    params: { version_id: versionId },
  })
  return data
}
