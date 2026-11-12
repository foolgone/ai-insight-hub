/**
 * API 路径常量（A-1：业务代码禁止散落字符串）。
 * 所有路径均相对于 baseURL `/api/v1`。
 */
export const API_PREFIX = '/api/v1'

export const endpoints = {
  auth: {
    login: '/auth/login',
    refresh: '/auth/refresh',
    logout: '/auth/logout',
    register: '/auth/register',
  },
  users: {
    me: '/users/me',
    password: '/users/me/password',
    llmCredential: '/users/me/llm-credential',
    llmCredentialVerify: '/users/me/llm-credential/verify',
    asrCredential: '/users/me/asr-credential',
  },
  datasources: {
    root: '/datasources',
    byId: id => `/datasources/${id}`,
    upload: id => `/datasources/${id}/upload`,
    clean: id => `/datasources/${id}/clean`,
    cleanedData: id => `/datasources/${id}/cleaned-data`,
    cleanedDataById: (id, dataId) => `/datasources/${id}/cleaned-data/${dataId}`,
    rawData: id => `/datasources/${id}/raw-data`,
    rawDataStructure: (id, rawId) => `/datasources/${id}/raw-data/${rawId}/structure`,
  },
  datasourceTypes: {
    root: '/datasource-types',
    byId: id => `/datasource-types/${id}`,
  },
  analysis: {
    quality: id => `/datasources/${id}/analyze/quality`,
    qualityResults: id => `/datasources/${id}/analysis/quality`,
    qualityReview: (id, resultId) => `/datasources/${id}/analysis/quality/${resultId}/review`,
    // 批次（一次评估任务）与批次对比
    qualityRuns: id => `/datasources/${id}/runs`,
    qualityRunCompare: (id, baseRunId, targetRunId) =>
      `/datasources/${id}/runs/${baseRunId}/compare/${targetRunId}`,
    insightRunCompare: (id, baseRunId, targetRunId) =>
      `/datasources/${id}/runs/${baseRunId}/insight-compare/${targetRunId}`,
    qualityIssues: id => `/datasources/${id}/analysis/quality/issues`,
    insights: id => `/datasources/${id}/analyze/insights`,
    insightsResults: id => `/datasources/${id}/analysis/insights`,
    summaries: id => `/datasources/${id}/analysis/summaries`,
  },
  knowledge: {
    extract: id => `/datasources/${id}/extract-knowledge`,
    faq: id => `/datasources/${id}/knowledge/faq`,
    faqById: (id, faqId) => `/datasources/${id}/knowledge/faq/${faqId}`,
    search: id => `/datasources/${id}/knowledge/search`,
    gaps: id => `/datasources/${id}/knowledge/gaps`,
    gapById: (id, gapId) => `/datasources/${id}/knowledge/gaps/${gapId}`,
    coverage: id => `/datasources/${id}/knowledge/coverage`,
  },
  reports: {
    byDatasource: id => `/datasources/${id}/reports`,
    byId: reportId => `/reports/${reportId}`,
    download: reportId => `/reports/${reportId}/download`,
  },
  tasks: {
    list: '/tasks',
    stream: '/tasks/stream',
    byId: taskId => `/tasks/${taskId}`,
    cancel: taskId => `/tasks/${taskId}/cancel`,
    retry: taskId => `/tasks/${taskId}/retry`,
  },
}
