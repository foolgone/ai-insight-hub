import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient } from './client'
import {
  createDataSource,
  deleteDataSource,
  getDataSource,
  listDataSources,
  updateDataSource,
  uploadDataSourceFile,
} from './datasources'

const ORIGINAL_ADAPTER = apiClient.defaults.adapter

describe('datasources API', () => {
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

  it('listDataSources 透传分页/筛选参数', async () => {
    await listDataSources({ page: 2, limit: 20, status: 'active' })

    expect(lastConfig.url).toBe('/datasources')
    expect(lastConfig.params).toEqual({ page: 2, limit: 20, status: 'active' })
  })

  it('getDataSource 请求详情路径', async () => {
    await getDataSource('ds-1')

    expect(lastConfig.url).toBe('/datasources/ds-1')
    expect(lastConfig.method).toBe('get')
  })

  it('createDataSource 提交名称/描述/类型', async () => {
    await createDataSource({ name: '客服1月', description: '批次', type: 'customer_service' })

    expect(lastConfig.url).toBe('/datasources')
    expect(lastConfig.method).toBe('post')
    expect(JSON.parse(lastConfig.data)).toEqual({
      name: '客服1月',
      description: '批次',
      type: 'customer_service',
    })
  })

  it('updateDataSource 使用 PATCH', async () => {
    await updateDataSource('ds-1', { name: '新名称' })

    expect(lastConfig.url).toBe('/datasources/ds-1')
    expect(lastConfig.method).toBe('patch')
    expect(JSON.parse(lastConfig.data)).toEqual({ name: '新名称' })
  })

  it('deleteDataSource 默认不带 force，force=true 时携带参数', async () => {
    await deleteDataSource('ds-1')
    expect(lastConfig.params).toBeUndefined()

    await deleteDataSource('ds-1', { force: true })
    expect(lastConfig.params).toEqual({ force: true })
  })

  it('uploadDataSourceFile 以 multipart 提交文件', async () => {
    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    await uploadDataSourceFile('ds-1', file)

    expect(lastConfig.url).toBe('/datasources/ds-1/upload')
    expect(lastConfig.data).toBeInstanceOf(FormData)
    expect(lastConfig.data.get('file')).toBe(file)
  })
})
