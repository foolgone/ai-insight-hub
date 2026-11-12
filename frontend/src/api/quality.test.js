import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from './client'
import {
  compareInsightRuns,
  compareQualityRuns,
  listQualityRuns,
  listQualityResults,
} from './quality'

const ORIGINAL_ADAPTER = apiClient.defaults.adapter

describe('quality API', () => {
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

  it('批次列表与对比路径正确', async () => {
    await listQualityRuns('ds-1', { limit: 20 })
    expect(lastConfig.url).toBe('/datasources/ds-1/runs')
    expect(lastConfig.params).toEqual({ limit: 20 })

    await compareQualityRuns('ds-1', 'run-a', 'run-b')
    expect(lastConfig.url).toBe('/datasources/ds-1/runs/run-a/compare/run-b')
  })

  it('洞察对比路径正确（#3）', async () => {
    await compareInsightRuns('ds-1', 'run-a', 'run-b')
    expect(lastConfig.url).toBe('/datasources/ds-1/runs/run-a/insight-compare/run-b')
  })

  it('评估结果列表透传查询参数', async () => {
    await listQualityResults('ds-1', { page: 2, limit: 10 })
    expect(lastConfig.url).toBe('/datasources/ds-1/analysis/quality')
    expect(lastConfig.params).toEqual({ page: 2, limit: 10 })
  })
})
