import { apiClient } from './client'
import { endpoints } from './endpoints'

/** 查询自己的语音转写配置（不含明文/密文）。 */
export async function getAsrCredentialStatus() {
  const { data } = await apiClient.get(endpoints.users.asrCredential)
  return data
}

/** 验证并保存（服务端强制连通性校验；失败返回 400，不入库）。 */
export async function saveAsrCredential({ baseUrl, apiKey, model, language }) {
  const { data } = await apiClient.put(endpoints.users.asrCredential, {
    base_url: baseUrl,
    api_key: apiKey,
    model,
    language,
  })
  return data
}

/** 删除配置（204，幂等）。 */
export async function deleteAsrCredential() {
  await apiClient.delete(endpoints.users.asrCredential)
}
