import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient } from './client'
import {
  cancelRagEvaluation,
  createRagEvaluation,
  getDatasetItem,
  getRagEvaluation,
  getRagTrace,
  listDatasetItems,
  listAllRagEvaluationResults,
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

describe('listAllRagEvaluationResults', () => {
  const originAdapter = apiClient.defaults.adapter
  let calls = 0

  afterEach(() => {
    apiClient.defaults.adapter = originAdapter
    calls = 0
  })

  it('按 page/limit 拉完，并按 maxRows 截断', async () => {
    const total = 250
    apiClient.defaults.adapter = async config => {
      calls += 1
      const page = Number(config.params?.page || 1)
      const limit = Number(config.params?.limit || 100)
      const start = (page - 1) * limit
      const items = Array.from(
        { length: Math.max(0, Math.min(limit, total - start)) },
        (_, index) => ({ id: `r-${start + index + 1}` })
      )
      return {
        data: {
          items,
          pagination: { page, limit, total, pages: Math.ceil(total / limit) },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }

    const all = await listAllRagEvaluationResults('run-1', { maxRows: 200 })

    expect(all.total).toBe(250)
    expect(all.loaded).toBe(200)
    expect(all.items).toHaveLength(200)
    expect(all.truncated).toBe(true)
    expect(calls).toBe(2)
  })

  it('429 时按 Retry-After 退避后重试', async () => {
    let attempts = 0
    apiClient.defaults.adapter = async config => {
      attempts += 1
      if (attempts === 1) {
        return Promise.reject({
          config,
          response: {
            status: 429,
            data: { error: { code: 'RATE_LIMIT_EXCEEDED', message: 'Too many requests' } },
            headers: { 'retry-after': '0' },
          },
        })
      }
      return {
        data: {
          items: [{ id: 'r-1' }],
          pagination: { page: 1, limit: 100, total: 1, pages: 1 },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }

    const all = await listAllRagEvaluationResults('run-1')

    expect(attempts).toBe(2)
    expect(all.items).toEqual([{ id: 'r-1' }])
  })
})
