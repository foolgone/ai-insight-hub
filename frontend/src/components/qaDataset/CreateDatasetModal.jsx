import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { Select } from '../Select'
import { Textarea } from '../Textarea'
import { createQaDataset } from '../../api/qaDatasets'
import { getErrorMessage } from '../../lib/errorMessages'

const SOURCE_OPTIONS = [
  { label: '混合（mixed）', value: 'mixed' },
  { label: '文档（doc）', value: 'doc' },
  { label: '对话（conv）', value: 'conv' },
]

/** 新建 QA 数据集。 */
export function CreateDatasetModal({ open, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [sourceType, setSourceType] = useState('mixed')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setName('')
    setDescription('')
    setSourceType('mixed')
    setError('')
    setSubmitting(false)
  }, [open])

  const handleSubmit = async () => {
    setError('')
    if (!name.trim()) {
      setError('请填写数据集名称')
      return
    }
    setSubmitting(true)
    try {
      const created = await createQaDataset({
        name: name.trim(),
        description: description.trim() || null,
        source_type: sourceType,
      })
      onCreated?.(created)
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
      title="新建 QA 数据集"
      size="md"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={submitting}>
            创建数据集
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-name">
            数据集名称
          </label>
          <Input
            id="qa-name"
            value={name}
            onChange={setName}
            placeholder="例如：售后政策评测集"
            maxLength={200}
            error={error && !name.trim() ? error : undefined}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-source">
            来源类型
          </label>
          <Select
            id="qa-source"
            ariaLabel="数据集来源类型"
            options={SOURCE_OPTIONS}
            value={sourceType}
            onChange={setSourceType}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-desc">
            描述（可选）
          </label>
          <Textarea
            id="qa-desc"
            value={description}
            onChange={setDescription}
            placeholder="说明数据用途、覆盖场景、版本口径等"
            maxLength={2000}
            rows={3}
          />
        </div>
        {error && name.trim() ? (
          <p role="alert" className="text-sm text-error-700">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  )
}
