import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient } from './client'
import {
  createFaq,
  deleteFaq,
  extractKnowledge,
  listFaq,
  listGaps,
  searchKnowledge,
  updateFaq,
} from './knowledge'
import { createReport, deleteReport, downloadReport, getReport, listReports } from './reports'
import { listQualityResults, reviewQuality, triggerQuality } from './quality'

const ORIGINAL_ADAPTER = apiClient.defaults.adapter

describe('P3 API（knowledge / reports / quality）', () => {
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

  it('knowledge 端点路径与参数', async () => {
    await listFaq('ds-1', { page: 1, category: '售后' })
    expect(lastConfig.url).toBe('/datasources/ds-1/knowledge/faq')
    expect(lastConfig.params).toEqual({ page: 1, category: '售后' })

    await searchKnowledge('ds-1', { q: '退款' })
    expect(lastConfig.url).toBe('/datasources/ds-1/knowledge/search')

    await listGaps('ds-1')
    expect(lastConfig.url).toBe('/datasources/ds-1/knowledge/gaps')

    await extractKnowledge('ds-1', { min_frequency: 5 })
    expect(lastConfig.method).toBe('post')
    expect(JSON.parse(lastConfig.data)).toEqual({ min_frequency: 5 })

    await createFaq('ds-1', { question: 'q', answer: 'a' })
    expect(lastConfig.method).toBe('post')

    await updateFaq('ds-1', 'f-1', { answer: 'b' })
    expect(lastConfig.url).toBe('/datasources/ds-1/knowledge/faq/f-1')
    expect(lastConfig.method).toBe('patch')

    await deleteFaq('ds-1', 'f-1')
    expect(lastConfig.method).toBe('delete')
  })

  it('reports 端点路径与下载 blob', async () => {
    await listReports('ds-1', { page: 1 })
    expect(lastConfig.url).toBe('/datasources/ds-1/reports')

    await createReport('ds-1', { title: 't', report_type: 'quality', format: 'markdown' })
    expect(lastConfig.method).toBe('post')

    await getReport('r-1')
    expect(lastConfig.url).toBe('/reports/r-1')

    await deleteReport('r-1')
    expect(lastConfig.method).toBe('delete')

    await downloadReport('r-1')
    expect(lastConfig.url).toBe('/reports/r-1/download')
    expect(lastConfig.responseType).toBe('blob')
  })

  it('quality 触发/列表/复核请求体', async () => {
    await triggerQuality('ds-1', {
      dimensions: ['accuracy'],
      threshold: 70,
    })
    expect(lastConfig.url).toBe('/datasources/ds-1/analyze/quality')
    expect(JSON.parse(lastConfig.data)).toEqual({
      data_ids: [],
      config: { dimensions: ['accuracy'], threshold: 70 },
    })

    await listQualityResults('ds-1', { page: 1 })
    expect(lastConfig.url).toBe('/datasources/ds-1/analysis/quality')

    await reviewQuality('ds-1', 'r-1', { decision: 'corrected', corrected_scores: { tone: 90 } })
    expect(lastConfig.url).toBe('/datasources/ds-1/analysis/quality/r-1/review')
    expect(JSON.parse(lastConfig.data)).toEqual({
      decision: 'corrected',
      corrected_scores: { tone: 90 },
    })
  })
})
