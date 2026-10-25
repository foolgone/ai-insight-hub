import { apiClient } from './client'
import { endpoints } from './endpoints'

/**
 * 报告列表（GET /datasources/{id}/reports）。
 * @param {string} datasourceId
 * @param {{ page?: number, limit?: number, report_type?: string, status?: string, sort?: string }} [params]
 */
export async function listReports(datasourceId, params = {}) {
  const { data } = await apiClient.get(endpoints.reports.byDatasource(datasourceId), { params })
  return data
}

/**
 * 生成报告（POST /datasources/{id}/reports，202）。
 * @param {string} datasourceId
 * @param {{ title: string, report_type: string, format: string, config?: Object }} payload
 */
export async function createReport(datasourceId, payload) {
  const { data } = await apiClient.post(endpoints.reports.byDatasource(datasourceId), payload)
  return data
}

/**
 * 报告详情（GET /reports/{id}）。
 * @param {string} reportId
 */
export async function getReport(reportId) {
  const { data } = await apiClient.get(endpoints.reports.byId(reportId))
  return data
}

/**
 * 删除报告（DELETE /reports/{id}，204）。
 * @param {string} reportId
 */
export async function deleteReport(reportId) {
  const { data } = await apiClient.delete(endpoints.reports.byId(reportId))
  return data
}

/**
 * 下载报告（GET /reports/{id}/download，返回 Blob）。
 * @param {string} reportId
 * @returns {Promise<Blob>}
 */
export async function downloadReport(reportId) {
  const { data } = await apiClient.get(endpoints.reports.download(reportId), {
    responseType: 'blob',
  })
  return data
}
