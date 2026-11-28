import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { publishQaDatasetVersion } from '../../api/qaDatasets'
import { getErrorMessage } from '../../lib/errorMessages'

/** 发布草稿版本；发布后不可变。 */
export function PublishVersionModal({ open, onClose, datasetId, version, onPublished }) {
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    setSubmitting(false)
  }, [open])

  const handlePublish = async () => {
    if (!datasetId || !version?.id) return
    setError('')
    setSubmitting(true)
    try {
      const published = await publishQaDatasetVersion(datasetId, version.id)
      await onPublished?.(published)
      onClose?.()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`发布版本 v${version?.version ?? ''}`}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handlePublish} loading={submitting}>
            确认发布
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-gray-700">
          发布后版本将变为只读，条目不能编辑或删除；如需修改请创建新版本。
        </p>
        <p className="rounded border border-warning-200 bg-warning-50 p-3 text-xs text-warning-800">
          当前版本：v{version?.version} · {version?.item_count ?? 0} 条。发布后不可撤销。
        </p>
        {error ? (
          <p role="alert" className="text-sm text-error-700">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  )
}
