import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { Textarea } from '../Textarea'
import { importQaDatasetItems } from '../../api/qaDatasets'
import { getErrorMessage } from '../../lib/errorMessages'

const TEMPLATE = JSON.stringify(
  [
    {
      item_key: 'Q001',
      query: '退款多久到账？',
      gold_answer: '审核通过后 3-5 个工作日原路退回。',
      gold_evidence: [
        {
          evidence_text: '退款将在审核通过后 3-5 个工作日内原路退回。',
          document_id: 'doc-refund',
          chunk_id: 'chunk-1',
          page_number: 1,
        },
      ],
      category: '售后',
      difficulty: 'easy',
      split: 'test',
    },
  ],
  null,
  2
)

/** 导入 JSON 条目；后端逐条校验，错误带 1-based 行号。 */
export function ImportItemsModal({ open, onClose, datasetId, version, onImported }) {
  const [text, setText] = useState('')
  const [topError, setTopError] = useState('')
  const [errors, setErrors] = useState([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setText('')
    setTopError('')
    setErrors([])
    setSubmitting(false)
  }, [open])

  const handleSubmit = async () => {
    setTopError('')
    setErrors([])
    let parsed
    try {
      parsed = JSON.parse(text || '[]')
    } catch (err) {
      setTopError(`JSON 解析失败：${err.message}`)
      return
    }
    if (!Array.isArray(parsed) || parsed.length === 0) {
      setTopError('请粘贴非空 JSON 数组')
      return
    }

    setSubmitting(true)
    try {
      const result = await importQaDatasetItems(datasetId, version.id, parsed)
      await onImported?.(result)
      onClose?.()
    } catch (err) {
      setTopError(getErrorMessage(err))
      const detailErrors = err?.details?.errors
      if (Array.isArray(detailErrors)) setErrors(detailErrors)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`导入条目 · v${version?.version ?? ''}`}
      size="lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={submitting}>
            校验并导入
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-gray-500">
            粘贴 JSON 数组；校验失败整批不写入。每条至少包含 `item_key` 与 `query`。
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setText(TEMPLATE)}
            disabled={submitting}
          >
            填入模板
          </Button>
        </div>

        <Textarea
          aria-label="JSON 条目"
          value={text}
          onChange={setText}
          placeholder={TEMPLATE}
          rows={12}
          className="font-mono text-xs"
          disabled={submitting}
        />

        {topError ? (
          <p role="alert" className="text-sm text-error-700">
            {topError}
          </p>
        ) : null}

        {errors.length ? (
          <div className="max-h-48 overflow-auto border border-error-200 bg-error-50">
            <table className="min-w-full text-xs">
              <caption className="sr-only">导入错误明细</caption>
              <thead className="border-b border-error-200 text-left text-error-700">
                <tr>
                  <th className="px-3 py-2">行号</th>
                  <th className="px-3 py-2">字段</th>
                  <th className="px-3 py-2">错误</th>
                </tr>
              </thead>
              <tbody>
                {errors.map((item, index) => (
                  <tr
                    key={`${item.index}-${item.field}-${index}`}
                    className="border-t border-error-100"
                  >
                    <td className="px-3 py-1.5 font-mono">{item.index}</td>
                    <td className="px-3 py-1.5 font-mono">{item.field}</td>
                    <td className="px-3 py-1.5">{item.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </Modal>
  )
}
