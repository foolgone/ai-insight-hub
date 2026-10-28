import { useState } from 'react'
import { Modal } from '../Modal'
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
 * 模型 API Key 设置弹窗（需求 §8；"验证并保存"为单一操作）。
 * Key 只存在于组件 state，关闭/保存成功即清空，不写任何 storage。
 */
export function APIKeyModal({ open, onClose, isDemo = false }) {
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const { data: status } = useCredentialStatusQuery({ enabled: open })
  const saveMutation = useSaveCredential()
  const deleteMutation = useDeleteCredential()

  const close = () => {
    setApiKey('')
    setShowKey(false)
    saveMutation.reset()
    deleteMutation.reset()
    onClose()
  }

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
    } catch {
      // 失败文案由下方 error 区域展示
    }
  }

  const error = saveMutation.error ?? deleteMutation.error

  const footer = (
    <>
      {status?.configured ? (
        <Button
          variant="danger"
          size="sm"
          loading={deleteMutation.isPending}
          onClick={handleDelete}
        >
          删除
        </Button>
      ) : null}
      <Button variant="ghost" size="sm" onClick={close}>
        取消
      </Button>
      <Button
        size="sm"
        loading={saveMutation.isPending}
        disabled={apiKey.trim().length < 12}
        onClick={handleSave}
      >
        验证并保存
      </Button>
    </>
  )

  return (
    <Modal open={open} onClose={close} title="模型 API Key 设置" size="sm" footer={footer}>
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
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded bg-gray-50 px-3 py-2 text-sm">
          <span className="font-mono text-gray-900">{status.key_hint}</span>
          <span
            className={
              status.status === 'active'
                ? 'rounded bg-green-100 px-2 py-0.5 text-xs text-green-700'
                : 'rounded bg-red-100 px-2 py-0.5 text-xs text-red-700'
            }
          >
            {status.status === 'active' ? '正常' : '无效'}
          </span>
          {status.verified_at ? (
            <span className="text-xs text-gray-500">
              验证于 {new Date(status.verified_at).toLocaleString()}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-start gap-2">
        <Input
          type={showKey ? 'text' : 'password'}
          value={apiKey}
          onChange={setApiKey}
          placeholder="sk-xxxxxxxxxxxxxxxx"
          autoComplete="new-password"
          error={error ? getErrorMessage(error) : undefined}
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
    </Modal>
  )
}
