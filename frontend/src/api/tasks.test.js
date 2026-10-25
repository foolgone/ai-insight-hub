import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient } from './client'
import { cancelTask, getTask, listTasks, retryTask } from './tasks'
import { getCleanedData, listCleanedData, startCleaning } from './cleaning'

const ORIGINAL_ADAPTER = apiClient.defaults.adapter

describe('tasks / cleaning API', () => {
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

  it('listTasks 透传过滤参数', async () => {
    await listTasks({ task_type: 'clean', status: 'running', page: 1 })

    expect(lastConfig.url).toBe('/tasks')
    expect(lastConfig.params).toEqual({ task_type: 'clean', status: 'running', page: 1 })
  })

  it('getTask/cancelTask/retryTask 路径正确', async () => {
    await getTask('t-1')
    expect(lastConfig.url).toBe('/tasks/t-1')

    await cancelTask('t-1')
    expect(lastConfig.url).toBe('/tasks/t-1/cancel')
    expect(lastConfig.method).toBe('post')

    await retryTask('t-1')
    expect(lastConfig.url).toBe('/tasks/t-1/retry')
  })

  it('startCleaning 提交 data_ids 与 config', async () => {
    await startCleaning('ds-1', {
      dataIds: ['d-1'],
      config: { remove_duplicates: false, normalize_text: true },
    })

    expect(lastConfig.url).toBe('/datasources/ds-1/clean')
    expect(JSON.parse(lastConfig.data)).toEqual({
      data_ids: ['d-1'],
      config: { remove_duplicates: false, normalize_text: true },
    })
  })

  it('startCleaning 默认空 data_ids', async () => {
    await startCleaning('ds-1')

    expect(JSON.parse(lastConfig.data)).toEqual({ data_ids: [] })
  })

  it('listCleanedData 透传筛选参数', async () => {
    await listCleanedData('ds-1', { quality_score_min: 60, has_issues: true })

    expect(lastConfig.url).toBe('/datasources/ds-1/cleaned-data')
    expect(lastConfig.params).toEqual({ quality_score_min: 60, has_issues: true })
  })

  it('getCleanedData 请求详情路径', async () => {
    await getCleanedData('ds-1', 'cd-1')

    expect(lastConfig.url).toBe('/datasources/ds-1/cleaned-data/cd-1')
  })
})
