import { describe, expect, it } from 'vitest'
import { API_PREFIX, endpoints } from './endpoints'

describe('endpoints', () => {
  it('基础前缀为 /api/v1', () => {
    expect(API_PREFIX).toBe('/api/v1')
  })

  it('认证与用户路径', () => {
    expect(endpoints.auth.login).toBe('/auth/login')
    expect(endpoints.auth.refresh).toBe('/auth/refresh')
    expect(endpoints.auth.logout).toBe('/auth/logout')
    expect(endpoints.auth.register).toBe('/auth/register')
    expect(endpoints.users.me).toBe('/users/me')
    expect(endpoints.users.password).toBe('/users/me/password')
  })

  it('数据源动态路径', () => {
    expect(endpoints.datasources.root).toBe('/datasources')
    expect(endpoints.datasources.byId('ds-1')).toBe('/datasources/ds-1')
    expect(endpoints.datasources.upload('ds-1')).toBe('/datasources/ds-1/upload')
    expect(endpoints.datasources.clean('ds-1')).toBe('/datasources/ds-1/clean')
    expect(endpoints.datasources.cleanedData('ds-1')).toBe('/datasources/ds-1/cleaned-data')
    expect(endpoints.datasources.cleanedDataById('ds-1', 'row-1')).toBe(
      '/datasources/ds-1/cleaned-data/row-1'
    )
  })

  it('分析路径', () => {
    expect(endpoints.analysis.quality('ds-1')).toBe('/datasources/ds-1/analyze/quality')
    expect(endpoints.analysis.qualityResults('ds-1')).toBe('/datasources/ds-1/analysis/quality')
    expect(endpoints.analysis.qualityReview('ds-1', 'r-1')).toBe(
      '/datasources/ds-1/analysis/quality/r-1/review'
    )
    expect(endpoints.analysis.insights('ds-1')).toBe('/datasources/ds-1/analyze/insights')
    expect(endpoints.analysis.insightsResults('ds-1')).toBe('/datasources/ds-1/analysis/insights')
  })

  it('知识库 / 报告 / 任务路径', () => {
    expect(endpoints.knowledge.extract('ds-1')).toBe('/datasources/ds-1/extract-knowledge')
    expect(endpoints.knowledge.faq('ds-1')).toBe('/datasources/ds-1/knowledge/faq')
    expect(endpoints.knowledge.faqById('ds-1', 'f-1')).toBe('/datasources/ds-1/knowledge/faq/f-1')
    expect(endpoints.knowledge.search('ds-1')).toBe('/datasources/ds-1/knowledge/search')
    expect(endpoints.knowledge.gaps('ds-1')).toBe('/datasources/ds-1/knowledge/gaps')
    expect(endpoints.reports.byDatasource('ds-1')).toBe('/datasources/ds-1/reports')
    expect(endpoints.reports.byId('rp-1')).toBe('/reports/rp-1')
    expect(endpoints.reports.download('rp-1')).toBe('/reports/rp-1/download')
    expect(endpoints.tasks.list).toBe('/tasks')
    expect(endpoints.tasks.byId('t-1')).toBe('/tasks/t-1')
    expect(endpoints.tasks.cancel('t-1')).toBe('/tasks/t-1/cancel')
    expect(endpoints.tasks.retry('t-1')).toBe('/tasks/t-1/retry')
  })
})
