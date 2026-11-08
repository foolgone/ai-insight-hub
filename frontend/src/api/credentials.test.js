import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from './client'
import * as asrApi from './asrCredential'
import * as llmApi from './llmCredential'
import * as typeApi from './datasourceTypes'

vi.mock('./client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('凭据与类型 API 封装', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('模型凭据：查询 / 保存 / 删除', async () => {
    apiClient.get.mockResolvedValue({ data: { configured: true } })
    await expect(llmApi.getCredentialStatus()).resolves.toEqual({ configured: true })
    expect(apiClient.get).toHaveBeenCalledWith('/users/me/llm-credential')

    apiClient.put.mockResolvedValue({ data: { configured: true } })
    await llmApi.saveCredential('sk-123456789012')
    expect(apiClient.put).toHaveBeenCalledWith('/users/me/llm-credential', {
      api_key: 'sk-123456789012',
      base_url: null,
      model: null,
    })

    apiClient.delete.mockResolvedValue({})
    await llmApi.deleteCredential()
    expect(apiClient.delete).toHaveBeenCalledWith('/users/me/llm-credential')
  })

  it('语音转写配置：camelCase 入参转 snake_case，删除走同一路径', async () => {
    apiClient.get.mockResolvedValue({ data: { configured: false } })
    await asrApi.getAsrCredentialStatus()
    expect(apiClient.get).toHaveBeenCalledWith('/users/me/asr-credential')

    apiClient.put.mockResolvedValue({ data: { configured: true } })
    await asrApi.saveAsrCredential({
      baseUrl: 'https://asr.example.com/v1',
      apiKey: 'asr-key-123',
      model: 'whisper-1',
      language: 'zh',
    })
    expect(apiClient.put).toHaveBeenCalledWith('/users/me/asr-credential', {
      base_url: 'https://asr.example.com/v1',
      api_key: 'asr-key-123',
      model: 'whisper-1',
      language: 'zh',
    })

    apiClient.delete.mockResolvedValue({})
    await asrApi.deleteAsrCredential()
    expect(apiClient.delete).toHaveBeenCalledWith('/users/me/asr-credential')
  })

  it('类型字典：列表参数、创建（省略空字段）、更新、删除', async () => {
    apiClient.get.mockResolvedValue({ data: { items: [] } })
    await typeApi.listDatasourceTypes({ includeInactive: true })
    expect(apiClient.get).toHaveBeenCalledWith('/datasource-types', {
      params: { include_inactive: true },
    })

    await typeApi.listDatasourceTypes()
    expect(apiClient.get).toHaveBeenLastCalledWith('/datasource-types', { params: undefined })

    apiClient.post.mockResolvedValue({ data: { id: 't-1' } })
    await typeApi.createDatasourceType({ label: '售后' })
    expect(apiClient.post).toHaveBeenCalledWith('/datasource-types', { label: '售后' })

    await typeApi.createDatasourceType({
      label: '售后',
      code: 'after_sales',
      description: '工单',
      sortOrder: 40,
    })
    expect(apiClient.post).toHaveBeenLastCalledWith('/datasource-types', {
      label: '售后',
      code: 'after_sales',
      description: '工单',
      sort_order: 40,
    })

    apiClient.patch.mockResolvedValue({ data: { id: 't-1' } })
    await typeApi.updateDatasourceType('t-1', { label: '售后服务' })
    expect(apiClient.patch).toHaveBeenCalledWith('/datasource-types/t-1', { label: '售后服务' })

    apiClient.delete.mockResolvedValue({})
    await typeApi.deleteDatasourceType('t-1')
    expect(apiClient.delete).toHaveBeenCalledWith('/datasource-types/t-1')
  })
})
