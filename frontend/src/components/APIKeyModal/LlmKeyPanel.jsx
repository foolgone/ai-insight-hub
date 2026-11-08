import { useState } from 'react'
import { Input } from '../Input'
import { Button } from '../Button'
import {
  useCredentialStatusQuery,
  useDeleteCredential,
  useSaveCredential,
} from '../../hooks/useLlmCredential'
import { getErrorMessage } from '../../lib/errorMessages'
import { DEMO_MODAL_NOTICE } from '../../lib/demoAccount'

/**
 * 模型 API Key 面板（需求 §8；"验证并保存"为单一操作）。
 * Key 只存在于组件 state，关闭/保存成功即清空，不写任何 storage。
 * 已配置时可在状态卡里直接「删除 Key」——二次确认后从服务器彻底删除。
 */
export function LlmKeyPanel({ isDemo = false }) {
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const { data: status } = useCredentialStatusQuery()
  const saveMutation = useSaveCredential()
  const deleteMutation = useDeleteCredential()

  const handleSave = async () => {
    try {
      await saveMutation.mutateAsync(apiKey.trim())
      setApiKey('')
    } catch {
      // 错误就地展示（保留输入便于修正）
    }
  }

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync()
      setApiKey('')
      setShowKey(false)
      setConfirmingDelete(false)
    } catch {
      // 失败文案在状态卡下方展示
    }
  }

  const error = saveMutation.error ?? deleteMutation.error

  return (
    <div>
      <p className="mb-3 text-sm text-gray-600">
        Key 仅加密保存在本系统，用于调用 DeepSeek，不会明文回显。
        <a
          className="ml-1 text-primary-600 hover:underline"
          href="https://platform.deepseek.com/api_keys"
          target="_blank"
          rel="noreferrer"
        >
          获取 Key →
        </a>
      </p>

      {isDemo ? (
        <p className="mb-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
          {DEMO_MODAL_NOTICE}
        </p>
      ) : null}

      {status?.configured ? (
        confirmingDelete ? (
          <div className="mb-3 border border-error-200 bg-error-50 px-3 py-2.5">
            <p className="text-sm font-medium text-error-700">从服务器删除这个 Key？</p>
            <p className="mt-1 text-xs text-error-600">
              删除后服务器上不再保留该 Key，AI 功能将不可用，直到重新配置。
            </p>
            <div className="mt-2.5 flex gap-2">
              <Button
                variant="danger"
                size="sm"
                loading={deleteMutation.isPending}
                onClick={handleDelete}
              >
                确认删除
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={deleteMutation.isPending}
                onClick={() => setConfirmingDelete(false)}
              >
                取消
              </Button>
            </div>
          </div>
        ) : (
          <div className="mb-3 border border-gray-200 bg-gray-50 px-3 py-2.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono text-gray-900">{status.key_hint}</span>
                  <span
                    className={
                      status.status === 'active'
                        ? 'bg-green-100 px-2 py-0.5 text-[11px] text-green-700'
                        : 'bg-red-100 px-2 py-0.5 text-[11px] text-red-700'
                    }
                  >
                    {status.status === 'active' ? '正常' : '无效'}
                  </span>
                </div>
                <p className="mt-1 font-mono text-[11px] text-gray-500">
                  已加密存储在服务器
                  {status.verified_at
                    ? ` · 验证于 ${new Date(status.verified_at).toLocaleString()}`
                    : ''}
                </p>
              </div>
              <Button
                variant="danger"
                size="sm"
                className="shrink-0"
                onClick={() => setConfirmingDelete(true)}
              >
                删除 Key
              </Button>
            </div>
          </div>
        )
      ) : null}

      {deleteMutation.error ? (
        <p className="mb-3 text-xs text-error-600">{getErrorMessage(deleteMutation.error)}</p>
      ) : null}

      <div className="flex items-start gap-2">
        <Input
          type={showKey ? 'text' : 'password'}
          value={apiKey}
          onChange={setApiKey}
          placeholder="sk-xxxxxxxxxxxxxxxx"
          autoComplete="new-password"
          helperText={status?.configured ? '输入新的 Key 可直接覆盖现有配置' : undefined}
          error={saveMutation.error ? getErrorMessage(saveMutation.error) : undefined}
        />
        <Button
          variant="outline"
          size="md"
          aria-label={showKey ? '隐藏 API Key' : '显示 API Key'}
          onClick={() => setShowKey(value => !value)}
        >
          {showKey ? '隐藏' : '显示'}
        </Button>
      </div>

      <footer className="mt-6 flex flex-col-reverse gap-2 border-t border-gray-100 pt-4 sm:flex-row sm:justify-end">
        <Button
          size="sm"
          loading={saveMutation.isPending}
          disabled={apiKey.trim().length < 12}
          onClick={handleSave}
        >
          验证并保存
        </Button>
      </footer>
    </div>
  )
}
