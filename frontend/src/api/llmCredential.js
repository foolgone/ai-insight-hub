import { apiClient } from './client'
import { endpoints } from './endpoints'

/** 查询自己的凭据状态（不含明文/密文）。 */
export async function getCredentialStatus() {
  const { data } = await apiClient.get(endpoints.users.llmCredential)
  return data
}

/** 验证并保存（服务端强制连通性校验；失败返回 400，不入库）。 */
export async function saveCredential(apiKey) {
  const { data } = await apiClient.put(endpoints.users.llmCredential, {
    api_key: apiKey,
    base_url: null,
    model: null,
  })
  return data
}

/** 删除凭据（204，幂等）。 */
export async function deleteCredential() {
  await apiClient.delete(endpoints.users.llmCredential)
}
