import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { LuUpload, LuX } from 'react-icons/lu'
import { Button } from '../Button'
import { Input } from '../Input'
import { Select } from '../Select'
import { createDataSource, uploadDataSourceFile } from '../../api/datasources'
import { useDatasourceTypeOptions } from '../../hooks/useDatasourceTypes'
import { useAsrCredentialStatusQuery } from '../../hooks/useAsrCredential'
import { openCredentialModal } from '../../lib/credentialGate'
import { getErrorMessage } from '../../lib/errorMessages'
import {
  MAX_UPLOAD_BYTES,
  MAX_UPLOAD_LABEL,
  MEDIA_LABEL,
  UPLOAD_ACCEPT,
  isMediaFile,
} from '../../lib/mediaFile'
import { notify } from '../../lib/toast'

function formatFileSize(size) {
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size} B`
}

/**
 * 新建数据源 Drawer（F-203）：步骤 1 基本信息 → 步骤 2 上传文件。
 * 创建成功后立即上传，上传返回 202 由清洗页轮询任务。
 * 支持文本与音视频；音视频需要用户先配置语音转写（BYOK）。
 * @param {{ open: boolean, onClose: () => void, onSuccess?: (datasource: Object) => void }} props
 */
export function CreateDataSourceDrawer({ open, onClose, onSuccess }) {
  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState('')
  const [file, setFile] = useState(null)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const { options: typeOptions } = useDatasourceTypeOptions({ includeInactive: false })
  const { data: asrStatus } = useAsrCredentialStatusQuery({ enabled: open })

  const mediaSelected = isMediaFile(file)
  const asrReady = asrStatus?.asr_enabled !== false && Boolean(asrStatus?.configured)

  useEffect(() => {
    if (!open) return
    setStep(1)
    setName('')
    setDescription('')
    setType('')
    setFile(null)
    setErrors({})
    setSubmitting(false)
  }, [open])

  // 类型字典异步加载：默认选中第一个可用类型
  useEffect(() => {
    if (!open || type) return
    if (typeOptions.length > 0) setType(typeOptions[0].value)
  }, [open, type, typeOptions])

  const goNext = () => {
    if (!name.trim()) {
      setErrors({ name: '请输入数据源名称' })
      return
    }
    if (!type) {
      setErrors({ type: '请选择数据源类型' })
      return
    }
    setErrors({})
    setStep(2)
  }

  const handleFileChange = event => {
    const selected = event.target.files?.[0]
    if (!selected) return
    if (selected.size > MAX_UPLOAD_BYTES) {
      setFile(null)
      setErrors({ file: `文件超过 ${MAX_UPLOAD_LABEL} 限制` })
      return
    }
    setFile(selected)
    setErrors({})
  }

  const handleSubmit = async () => {
    if (submitting) return
    if (!file) {
      setErrors({ file: '请选择要上传的文件' })
      return
    }
    if (isMediaFile(file) && !asrReady) {
      setErrors({ file: '音视频需要先配置语音转写服务' })
      return
    }

    setSubmitting(true)
    setErrors({})
    try {
      const created = await createDataSource({
        name: name.trim(),
        ...(description.trim() ? { description: description.trim() } : {}),
        type,
      })
      await uploadDataSourceFile(created.id, file)
      notify.success('数据源创建成功，已开始处理')
      onSuccess?.(created)
    } catch (error) {
      const message = getErrorMessage(error)
      setErrors({ form: message })
      notify.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={nextOpen => (nextOpen ? undefined : onClose())}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[480px] flex-col bg-white shadow-xl focus:outline-none"
        >
          <header className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-4">
            <div>
              <Dialog.Title className="text-lg font-semibold text-gray-900">
                新建数据源
              </Dialog.Title>
              <p className="mt-1 text-xs text-gray-500">
                上传对话数据文件（CSV/JSON/XLSX/TXT/音视频，≤ {MAX_UPLOAD_LABEL}）
              </p>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="关闭"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-gray-500 hover:bg-gray-100"
              >
                <LuX className="h-4 w-4" aria-hidden="true" />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-4">
            <ol className="mb-6 flex items-center gap-2 text-xs text-gray-500">
              <li className={step === 1 ? 'font-medium text-primary-600' : ''}>1. 基本信息</li>
              <li aria-hidden="true">→</li>
              <li className={step === 2 ? 'font-medium text-primary-600' : ''}>2. 上传文件</li>
            </ol>

            {errors.form ? (
              <div
                role="alert"
                className="mb-4 rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
              >
                {errors.form}
              </div>
            ) : null}

            {step === 1 ? (
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="datasource-name"
                    className="mb-1 block text-sm font-medium text-gray-700"
                  >
                    名称 <span className="text-error-500">*</span>
                  </label>
                  <Input
                    id="datasource-name"
                    value={name}
                    onChange={value => setName(value)}
                    placeholder="如：客服对话-2026年1月"
                    error={errors.name}
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label
                    htmlFor="datasource-description"
                    className="mb-1 block text-sm font-medium text-gray-700"
                  >
                    描述
                  </label>
                  <Input
                    id="datasource-description"
                    value={description}
                    onChange={value => setDescription(value)}
                    placeholder="可选，用于区分数据批次"
                    disabled={submitting}
                  />
                </div>
                <div>
                  <span className="mb-1 block text-sm font-medium text-gray-700">类型</span>
                  <Select
                    ariaLabel="数据源类型"
                    options={typeOptions}
                    value={type}
                    onChange={value => setType(value)}
                    error={errors.type}
                    disabled={submitting}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <label
                  htmlFor="datasource-file"
                  className="mb-1 block text-sm font-medium text-gray-700"
                >
                  数据文件 <span className="text-error-500">*</span>
                </label>
                <input
                  id="datasource-file"
                  type="file"
                  accept={UPLOAD_ACCEPT}
                  onChange={handleFileChange}
                  disabled={submitting}
                  className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-md file:border-0 file:bg-primary-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-700 hover:file:bg-primary-100"
                />
                {errors.file ? (
                  <p role="alert" className="text-xs text-error-600">
                    {errors.file}
                  </p>
                ) : null}
                {file ? (
                  <div className="flex items-center gap-2 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                    <LuUpload className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate">{file.name}</span>
                    <span className="shrink-0 text-gray-400">{formatFileSize(file.size)}</span>
                  </div>
                ) : null}
                {mediaSelected && !asrReady ? (
                  <div className="border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    <p>
                      检测到音视频文件：请先配置语音转写服务（服务地址 + API Key），否则无法转写。
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        onClose()
                        openCredentialModal('asr')
                      }}
                      className="mt-2 border border-amber-400 px-2 py-1 font-medium text-amber-900 transition-colors hover:bg-amber-100"
                    >
                      去配置语音转写
                    </button>
                  </div>
                ) : null}
                <p className="text-xs text-gray-500">
                  支持 CSV / JSON / XLSX / TXT / {MEDIA_LABEL}，单文件 ≤ {MAX_UPLOAD_LABEL}；
                  音视频会先转写为文本再进入清洗，建议上传双声道通话录音（左客户 / 右坐席）。
                </p>
              </div>
            )}
          </div>

          <footer className="flex items-center justify-end gap-2 border-t border-gray-100 px-6 py-4">
            {step === 1 ? (
              <>
                <Button variant="secondary" onClick={onClose} disabled={submitting}>
                  取消
                </Button>
                <Button onClick={goNext} disabled={submitting}>
                  下一步
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" onClick={() => setStep(1)} disabled={submitting}>
                  上一步
                </Button>
                <Button
                  onClick={handleSubmit}
                  loading={submitting}
                  disabled={submitting || (mediaSelected && !asrReady)}
                >
                  创建并上传
                </Button>
              </>
            )}
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
