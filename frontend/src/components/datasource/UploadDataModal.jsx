import { useEffect, useState } from 'react'
import { LuUpload } from 'react-icons/lu'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { useUploadDataSourceFile } from '../../hooks/useDataSources'
import { useAsrCredentialStatusQuery } from '../../hooks/useAsrCredential'
import { getErrorMessage } from '../../lib/errorMessages'
import { openCredentialModal } from '../../lib/credentialGate'
import { notify } from '../../lib/toast'

const ACCEPT = '.csv,.json,.xlsx,.txt,.mp3,.wav,.m4a,.mp4,.mov'
const MEDIA_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.mp4', '.mov']
const MAX_FILE_SIZE = 50 * 1024 * 1024

function isMediaFile(file) {
  if (!file) return false
  const name = file.name.toLowerCase()
  return MEDIA_EXTENSIONS.some(ext => name.endsWith(ext))
}

/**
 * 给已有数据源追加数据文件（F-204）：上传成功后进入清洗队列（202）。
 * 音视频需要用户先配置自己的语音转写服务（BYOK），未配置时给出就地提示。
 * @param {{ datasource: Object|null, open: boolean, onClose: () => void }} props
 */
export function UploadDataModal({ datasource, open, onClose }) {
  const mutation = useUploadDataSourceFile()
  const { data: asrStatus } = useAsrCredentialStatusQuery({ enabled: open })
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setFile(null)
    setError('')
  }, [open])

  const mediaSelected = isMediaFile(file)
  const asrReady = asrStatus?.asr_enabled !== false && Boolean(asrStatus?.configured)

  useEffect(() => {
    if (!open) return
    setFile(null)
    setError('')
  }, [open])

  const handleFileChange = event => {
    const selected = event.target.files?.[0]
    if (!selected) return
    if (selected.size > MAX_FILE_SIZE) {
      setFile(null)
      setError('文件超过 50MB 限制')
      return
    }
    setFile(selected)
    setError('')
  }

  const handleSubmit = async () => {
    if (!file) {
      setError('请选择要上传的文件')
      return
    }
    try {
      await mutation.mutateAsync({ id: datasource.id, file })
      notify.success('文件已上传，清洗任务已入队')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`上传数据：${datasource?.name || ''}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button
            icon={<LuUpload className="h-4 w-4" />}
            onClick={handleSubmit}
            loading={mutation.isPending}
            disabled={mutation.isPending || (mediaSelected && !asrReady)}
          >
            上传
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error ? (
          <div
            role="alert"
            className="rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
          >
            {error}
          </div>
        ) : null}
        <label htmlFor="upload-datasource-file" className="block text-sm font-medium text-gray-700">
          数据文件
        </label>
        <input
          id="upload-datasource-file"
          type="file"
          accept={ACCEPT}
          onChange={handleFileChange}
          disabled={mutation.isPending}
          className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-md file:border-0 file:bg-primary-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-700 hover:file:bg-primary-100"
        />
        {file ? (
          <p className="flex items-center gap-2 text-xs text-gray-600">
            <LuUpload className="h-4 w-4 text-gray-400" aria-hidden="true" />
            {file.name}
          </p>
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
          支持 CSV / JSON / XLSX / TXT / MP3 / WAV / M4A / MP4 / MOV，单文件 ≤ 50MB；
          音视频会先转写为文本再进入清洗；建议上传双声道通话录音（左客户 / 右坐席）。
        </p>
      </div>
    </Modal>
  )
}
