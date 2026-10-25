import { useEffect, useState } from 'react'
import { LuUpload } from 'react-icons/lu'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { useUploadDataSourceFile } from '../../hooks/useDataSources'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const ACCEPT = '.csv,.json,.xlsx,.txt'
const MAX_FILE_SIZE = 50 * 1024 * 1024

/**
 * 给已有数据源追加数据文件（F-204）：上传成功后进入清洗队列（202）。
 * @param {{ datasource: Object|null, open: boolean, onClose: () => void }} props
 */
export function UploadDataModal({ datasource, open, onClose }) {
  const mutation = useUploadDataSourceFile()
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')

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
            disabled={mutation.isPending}
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
        <p className="text-xs text-gray-500">
          支持 CSV / JSON / XLSX / TXT，单文件 ≤ 50MB；上传后自动入队清洗。
        </p>
      </div>
    </Modal>
  )
}
