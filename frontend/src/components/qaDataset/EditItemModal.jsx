import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { Select } from '../Select'
import { Textarea } from '../Textarea'
import { updateQaDatasetItem } from '../../api/qaDatasets'
import { getErrorMessage } from '../../lib/errorMessages'

const SPLIT_OPTIONS = [
  { label: 'test', value: 'test' },
  { label: 'valid', value: 'valid' },
  { label: 'train', value: 'train' },
]

/** 编辑 draft 条目（发布版本只读）。 */
export function EditItemModal({ open, onClose, datasetId, versionId, item, onSaved }) {
  const [query, setQuery] = useState('')
  const [goldAnswer, setGoldAnswer] = useState('')
  const [split, setSplit] = useState('test')
  const [category, setCategory] = useState('')
  const [difficulty, setDifficulty] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open || !item) return
    setQuery(item.query || '')
    setGoldAnswer(item.gold_answer || '')
    setSplit(item.split || 'test')
    setCategory(item.category || '')
    setDifficulty(item.difficulty || '')
    setError('')
    setSubmitting(false)
  }, [open, item])

  const handleSubmit = async () => {
    if (!query.trim()) {
      setError('query 不能为空')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const updated = await updateQaDatasetItem(datasetId, versionId, item.id, {
        query: query.trim(),
        gold_answer: goldAnswer.trim() || null,
        split,
        category: category.trim() || null,
        difficulty: difficulty.trim() || null,
      })
      await onSaved?.(updated)
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
      title={`编辑条目 · ${item?.item_key ?? ''}`}
      size="md"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={submitting}>
            保存
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-edit-query">
            Query
          </label>
          <Textarea
            id="qa-edit-query"
            value={query}
            onChange={setQuery}
            rows={3}
            maxLength={10000}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-edit-answer">
            标准答案（可选）
          </label>
          <Textarea
            id="qa-edit-answer"
            value={goldAnswer}
            onChange={setGoldAnswer}
            rows={3}
            maxLength={20000}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="qa-edit-split">
              Split
            </label>
            <Select
              id="qa-edit-split"
              ariaLabel="条目 split"
              options={SPLIT_OPTIONS}
              value={split}
              onChange={setSplit}
            />
          </div>
          <div>
            <label
              className="mb-1 block text-sm font-medium text-gray-700"
              htmlFor="qa-edit-category"
            >
              分类（可选）
            </label>
            <Input id="qa-edit-category" value={category} onChange={setCategory} maxLength={100} />
          </div>
        </div>
        <div>
          <label
            className="mb-1 block text-sm font-medium text-gray-700"
            htmlFor="qa-edit-difficulty"
          >
            难度（可选）
          </label>
          <Input
            id="qa-edit-difficulty"
            value={difficulty}
            onChange={setDifficulty}
            maxLength={20}
            placeholder="easy / medium / hard"
          />
        </div>
        <p className="text-xs text-gray-500">证据（gold_evidence）编辑放在 P1；当前保留原值。</p>
        {error ? (
          <p role="alert" className="text-sm text-error-700">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  )
}
