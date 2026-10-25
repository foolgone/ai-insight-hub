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
  },
  datasources: {
    root: '/datasources',
    byId: id => `/datasources/${id}`,
    upload: id => `/datasources/${id}/upload`,
    clean: id => `/datasources/${id}/clean`,
    cleanedData: id => `/datasources/${id}/cleaned-data`,
    cleanedDataById: (id, dataId) => `/datasources/${id}/cleaned-data/${dataId}`,
  },
  analysis: {
    quality: id => `/datasources/${id}/analyze/quality`,
    qualityResults: id => `/datasources/${id}/analysis/quality`,
    qualityReview: (id, resultId) => `/datasources/${id}/analysis/quality/${resultId}/review`,
    insights: id => `/datasources/${id}/analyze/insights`,
    insightsResults: id => `/datasources/${id}/analysis/insights`,
  },
  knowledge: {
    extract: id => `/datasources/${id}/extract-knowledge`,
    faq: id => `/datasources/${id}/knowledge/faq`,
    faqById: (id, faqId) => `/datasources/${id}/knowledge/faq/${faqId}`,
    search: id => `/datasources/${id}/knowledge/search`,
    gaps: id => `/datasources/${id}/knowledge/gaps`,
  },
  reports: {
    byDatasource: id => `/datasources/${id}/reports`,
    byId: reportId => `/reports/${reportId}`,
    download: reportId => `/reports/${reportId}/download`,
  },
  tasks: {
    list: '/tasks',
    byId: taskId => `/tasks/${taskId}`,
    cancel: taskId => `/tasks/${taskId}/cancel`,
    retry: taskId => `/tasks/${taskId}/retry`,
  },
}
