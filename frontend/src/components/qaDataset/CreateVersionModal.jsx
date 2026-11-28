import { useEffect, useMemo, useState } from 'react'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { Select } from '../Select'
import { Textarea } from '../Textarea'
import { createQaDatasetVersion } from '../../api/qaDatasets'
import { getErrorMessage } from '../../lib/errorMessages'

const STATUS_LABELS = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}

/** 新建数据集版本；可从旧版本 copy-on-write。 */
export function CreateVersionModal({ open, onClose, dataset, versions = [], onCreated }) {
  const [note, setNote] = useState('')
  const [fromVersionId, setFromVersionId] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setNote('')
    setFromVersionId('')
    setError('')
    setSubmitting(false)
  }, [open])

  const options = useMemo(
    () => [
      { label: '空白版本', value: '' },
      ...versions.map(version => ({
        label: `v${version.version} · ${STATUS_LABELS[version.status] || version.status} · ${version.item_count} 条`,
        value: version.id,
      })),
    ],
    [versions]
  )

  const handleSubmit = async () => {
    if (!dataset?.id) return
    setError('')
    setSubmitting(true)
    try {
      const created = await createQaDatasetVersion(dataset.id, {
        note: note.trim() || null,
        from_version_id: fromVersionId || null,
      })
      await onCreated?.(created)
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
      title="新建草稿版本"
      size="md"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={submitting}>
            创建草稿
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-from-version">
            复制自版本（可选）
          </label>
          <Select
            id="qa-from-version"
            ariaLabel="复制自版本"
            options={options}
            value={fromVersionId}
            onChange={setFromVersionId}
          />
          <p className="mt-1 text-xs text-gray-500">
            从旧版本复制会生成新的 draft，旧版本保持不变；不选则创建空版本。
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-version-note">
            版本说明（可选）
          </label>
          <Textarea
            id="qa-version-note"
            value={note}
            onChange={setNote}
            placeholder="例如：补充退款时效 10 条"
            maxLength={2000}
            rows={3}
          />
        </div>
        {error ? (
          <p role="alert" className="text-sm text-error-700">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  )
}
