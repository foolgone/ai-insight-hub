import { useState } from 'react'
import { Input } from '../Input'
import { Select } from '../Select'
import { Button } from '../Button'
import {
  useAsrCredentialStatusQuery,
  useDeleteAsrCredential,
  useSaveAsrCredential,
} from '../../hooks/useAsrCredential'
import { getErrorMessage } from '../../lib/errorMessages'

const LANGUAGE_OPTIONS = [
  { label: '中文', value: 'zh' },
  { label: '英文', value: 'en' },
  { label: '粤语', value: 'yue' },
  { label: '日文', value: 'ja' },
  { label: '韩文', value: 'ko' },
  { label: '自动识别', value: 'auto' },
]

const LABEL_CLASS = 'mb-1 block font-mono text-[10px] uppercase tracking-[0.14em] text-gray-500'

/**
 * 语音转写（ASR）配置面板：地址 / Key / 模型 / 语言全部由用户填写，
 * 加密存服务端（与模型 API Key 同一套凭据表），保存前服务端会真调一次转写接口。
 * 已配置时可在状态卡里直接「删除配置」——二次确认后从服务器彻底删除。
 */
export function AsrKeyPanel() {
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [language, setLanguage] = useState('zh')
  const [showKey, setShowKey] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const { data: status } = useAsrCredentialStatusQuery()
  const saveMutation = useSaveAsrCredential()
  const deleteMutation = useDeleteAsrCredential()

  const handleSave = async () => {
    try {
      await saveMutation.mutateAsync({
        baseUrl: baseUrl.trim(),
        apiKey: apiKey.trim(),
        model: model.trim(),
        language,
      })
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

  const canSave =
    baseUrl.trim().length > 0 && apiKey.trim().length >= 8 && model.trim().length > 0

  return (
    <div>
      <p className="mb-3 text-sm text-gray-600">
        用于把客服通话录音/视频转成文字，再进入清洗与评估。支持任意 OpenAI 兼容的
        <span className="mx-1 font-mono text-[12px] text-gray-900">/audio/transcriptions</span>
        服务（OpenAI / Groq / SiliconFlow / 自建）。Key 加密保存在本系统，不会明文回显。
      </p>

      {status?.configured ? (
        confirmingDelete ? (
          <div className="mb-4 border border-error-200 bg-error-50 px-3 py-2.5">
            <p className="text-sm font-medium text-error-700">从服务器删除语音转写配置？</p>
            <p className="mt-1 text-xs text-error-600">
              删除后服务器上不再保留该 Key 与服务地址，音视频上传将被拒绝，直到重新配置。
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
          <div className="mb-4 border border-gray-200 bg-gray-50 px-3 py-2.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="truncate font-mono text-[12px] text-gray-900">
                    {status.base_url}
                  </span>
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
                <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-gray-500">
                  <span>model {status.model}</span>
                  <span>lang {status.language || 'zh'}</span>
                  <span>key {status.key_hint}</span>
                  {status.verified_at ? (
                    <span>验证于 {new Date(status.verified_at).toLocaleString()}</span>
                  ) : null}
                </p>
              </div>
              <Button
                variant="danger"
                size="sm"
                className="shrink-0"
                onClick={() => setConfirmingDelete(true)}
              >
                删除配置
              </Button>
            </div>
          </div>
        )
      ) : null}

      {deleteMutation.error ? (
        <p className="mb-3 text-xs text-error-600">{getErrorMessage(deleteMutation.error)}</p>
      ) : null}

      <div className="space-y-3">
        <div>
          <label htmlFor="asr-base-url" className={LABEL_CLASS}>
            服务地址
          </label>
          <Input
            id="asr-base-url"
            value={baseUrl}
            onChange={setBaseUrl}
            placeholder="https://api.siliconflow.cn/v1"
            helperText="必须以 https:// 开头；填写到 /v1 这一层即可"
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="asr-model" className={LABEL_CLASS}>
              模型
            </label>
            <Input id="asr-model" value={model} onChange={setModel} placeholder="whisper-1" />
          </div>
          <div>
            <label htmlFor="asr-language" className={LABEL_CLASS}>
              识别语言
            </label>
            <Select
              id="asr-language"
              ariaLabel="识别语言"
              options={LANGUAGE_OPTIONS}
              value={language}
              onChange={setLanguage}
            />
          </div>
        </div>

        <div>
          <label htmlFor="asr-api-key" className={LABEL_CLASS}>
            API Key
          </label>
          <div className="flex items-start gap-2">
            <Input
              id="asr-api-key"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={setApiKey}
              placeholder="sk-xxxxxxxxxxxxxxxx"
              autoComplete="new-password"
              error={saveMutation.error ? getErrorMessage(saveMutation.error) : undefined}
            />
            <Button
              variant="outline"
              size="md"
              aria-label={showKey ? '隐藏转写 Key' : '显示转写 Key'}
              onClick={() => setShowKey(value => !value)}
            >
              {showKey ? '隐藏' : '显示'}
            </Button>
          </div>
        </div>
      </div>

      <p className="mt-3 text-xs text-gray-500">
        建议上传双声道通话录音（左声道客户 / 右声道坐席），可自动配对成一轮问答；
        单声道会转成整段文本并标记说话人未知。
      </p>

      <footer className="mt-6 flex flex-col-reverse gap-2 border-t border-gray-100 pt-4 sm:flex-row sm:justify-end">
        <Button
          size="sm"
          loading={saveMutation.isPending}
          disabled={!canSave}
          onClick={handleSave}
        >
          验证并保存
        </Button>
      </footer>
    </div>
  )
}
