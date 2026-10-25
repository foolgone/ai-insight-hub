import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { RadioGroup } from '../Radio'
import { Textarea } from '../Textarea'
import { useReviewQuality } from '../../hooks/useQuality'
import { EVALUATION_DIMENSIONS } from '../../lib/evaluation'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const DECISIONS = [
  { label: '通过', value: 'approved' },
  { label: '驳回', value: 'rejected' },
  { label: '修正分数', value: 'corrected' },
]

/**
 * 人工复核（F-307）：approved / rejected / corrected；后端只重算总分，不重算 quality_level。
 * @param {{ open: boolean, onClose: () => void, datasourceId: string|null, result: Object|null }} props
 */
export function ReviewModal({ open, onClose, datasourceId, result }) {
  const mutation = useReviewQuality()
  const [decision, setDecision] = useState('approved')
  const [note, setNote] = useState('')
  const [scores, setScores] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !result) return
    setDecision('approved')
    setNote('')
    setError('')
    setScores(
      Object.fromEntries(
        EVALUATION_DIMENSIONS.map(item => [
          item.key,
          Number(result.dimensions?.[item.key]?.score ?? 0),
        ])
      )
    )
  }, [open, result])

  const handleSubmit = async () => {
    if (!datasourceId || !result) {
      setError('缺少评估结果')
      return
    }
    try {
      await mutation.mutateAsync({
        datasourceId,
        resultId: result.id,
        payload: {
          decision,
          ...(note.trim() ? { note: note.trim() } : {}),
          ...(decision === 'corrected'
            ? {
                corrected_scores: Object.fromEntries(
                  Object.entries(scores).map(([key, value]) => [key, Number(value) || 0])
                ),
              }
            : {}),
        },
      })
      notify.success('复核结果已提交')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="人工复核"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending} disabled={mutation.isPending}>
            提交复核
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? (
          <div
            role="alert"
            className="rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
          >
            {error}
          </div>
        ) : null}

        <div>
          <span className="mb-2 block text-sm font-medium text-gray-700">复核结论</span>
          <RadioGroup
            options={DECISIONS}
            value={decision}
            onChange={setDecision}
            ariaLabel="复核结论"
            disabled={mutation.isPending}
          />
        </div>

        {decision === 'corrected' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {EVALUATION_DIMENSIONS.map(item => (
              <div key={item.key}>
                <label
                  htmlFor={`review-${item.key}`}
                  className="mb-1 block text-sm font-medium text-gray-700"
                >
                  {item.label}
                </label>
                <Input
                  id={`review-${item.key}`}
                  type="number"
                  value={String(scores[item.key] ?? '')}
                  onChange={value => setScores(current => ({ ...current, [item.key]: value }))}
                  disabled={mutation.isPending}
                />
              </div>
            ))}
          </div>
        ) : null}

        <div>
          <label htmlFor="review-note" className="mb-1 block text-sm font-medium text-gray-700">
            备注
          </label>
          <Textarea
            id="review-note"
            value={note}
            onChange={setNote}
            placeholder="可填写复核说明（≤1000 字）"
            maxLength={1000}
            disabled={mutation.isPending}
          />
        </div>
      </div>
    </Modal>
  )
}
