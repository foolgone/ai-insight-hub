import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient } from './client'
import {
  cancelRagEvaluation,
  createRagEvaluation,
  getDatasetItem,
  getRagEvaluation,
  getRagTrace,
  listDatasetItems,
  listDatasetVersions,
  listDatasets,
  listRagEvaluationFailures,
  listRagEvaluationResults,
  listRagEvaluations,
  retryRagEvaluation,
} from './ragEvaluations'

const ORIGINAL_ADAPTER = apiClient.defaults.adapter

describe('ragEvaluations API', () => {
  let lastConfig

  beforeEach(() => {
    lastConfig = null
    apiClient.defaults.adapter = async config => {
      lastConfig = config
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
    }
  })

  afterEach(() => {
    apiClient.defaults.adapter = ORIGINAL_ADAPTER
  })

  it('Run 列表/详情/结果/失败路径正确', async () => {
    await listRagEvaluations({ page: 2, status: 'completed' })
    expect(lastConfig.url).toBe('/rag/evaluations')
    expect(lastConfig.params).toEqual({ page: 2, status: 'completed' })

    await getRagEvaluation('run-1')
    expect(lastConfig.url).toBe('/rag/evaluations/run-1')

    await listRagEvaluationResults('run-1', { limit: 100 })
    expect(lastConfig.url).toBe('/rag/evaluations/run-1/results')
    expect(lastConfig.params).toEqual({ limit: 100 })

    await listRagEvaluationFailures('run-1', { limit: 20 })
    expect(lastConfig.url).toBe('/rag/evaluations/run-1/failures')
  })

  it('创建/重试/取消走 POST', async () => {
    await createRagEvaluation({ dataset_version_id: 'v-1', execution_mode: 'query' })
    expect(lastConfig.url).toBe('/rag/evaluations')
    expect(lastConfig.method).toBe('post')

    await retryRagEvaluation('run-1')
    expect(lastConfig.url).toBe('/rag/evaluations/run-1/retry')

    await cancelRagEvaluation('run-1')
    expect(lastConfig.url).toBe('/rag/evaluations/run-1/cancel')
  })

  it('Trace 与数据集只读路径正确', async () => {
    await getRagTrace('trace-1')
    expect(lastConfig.url).toBe('/rag/traces/trace-1')

    await listDatasets({ limit: 100 })
    expect(lastConfig.url).toBe('/qa-datasets')

    await listDatasetVersions('ds-1')
    expect(lastConfig.url).toBe('/qa-datasets/ds-1/versions')

    await listDatasetItems('ds-1', 'v-1', { limit: 100 })
    expect(lastConfig.url).toBe('/qa-datasets/ds-1/versions/v-1/items')

    await getDatasetItem('ds-1', 'v-1', 'item-1')
    expect(lastConfig.url).toBe('/qa-datasets/ds-1/versions/v-1/items/item-1')
  })
})
