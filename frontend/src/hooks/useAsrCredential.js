import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as asrCredentialApi from '../api/asrCredential'
import { notify } from '../lib/toast'

export const asrCredentialKeys = {
  all: ['asr-credential'],
  status: () => ['asr-credential', 'status'],
}

/** 语音转写配置状态（设置弹窗 / 上传弹窗共用）。 */
export function useAsrCredentialStatusQuery({ enabled = true, ...options } = {}) {
  return useQuery({
    queryKey: asrCredentialKeys.status(),
    queryFn: asrCredentialApi.getAsrCredentialStatus,
    enabled,
    staleTime: 30_000,
    ...options,
  })
}

/** 验证并保存：错误交给调用方就地展示（弹窗内），不额外弹 toast。 */
export function useSaveAsrCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: asrCredentialApi.saveAsrCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: asrCredentialKeys.all })
    },
  })
}

/** 删除：成功后刷新状态并提示。 */
export function useDeleteAsrCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: asrCredentialApi.deleteAsrCredential,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: asrCredentialKeys.all })
      notify.success('语音转写配置已删除')
    },
  })
}
