import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as llmCredentialApi from '../api/llmCredential'
import { notify } from '../lib/toast'

export const credentialKeys = {
  all: ['llm-credential'],
  status: () => ['llm-credential', 'status'],
}

/** 凭据状态（用户菜单入口 + 设置弹窗共用）。 */
export function useCredentialStatusQuery({ enabled = true, ...options } = {}) {
  return useQuery({
    queryKey: credentialKeys.status(),
    queryFn: llmCredentialApi.getCredentialStatus,
    enabled,
    staleTime: 30_000,
    ...options,
  })
}

/** 验证并保存：错误交给调用方就地展示（Modal 内），不额外弹 toast。 */
export function useSaveCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: llmCredentialApi.saveCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: credentialKeys.all })
    },
  })
}

/** 删除：成功后刷新状态并提示。 */
export function useDeleteCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: llmCredentialApi.deleteCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: credentialKeys.all })
      notify.success('API Key 已删除')
    },
  })
}
