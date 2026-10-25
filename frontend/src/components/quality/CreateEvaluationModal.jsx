import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Checkbox } from '../Checkbox'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { useTriggerQuality } from '../../hooks/useQuality'
import { EVALUATION_DIMENSIONS as DIMENSIONS } from '../../lib/evaluation'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

/**
 * 新建评估任务（F-306）：请求体 `{data_ids, config:{dimensions, threshold}}`（A-9，无 include_kb）。
 * @param {{ open: boolean, onClose: () => void, datasourceId?: string|null }} props
 */
export function CreateEvaluationModal({ open, onClose, datasourceId = null }) {
  const mutation = useTriggerQuality()
  const [dimensions, setDimensions] = useState(DIMENSIONS.map(item => item.key))
  const [threshold, setThreshold] = useState('70')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setDimensions(DIMENSIONS.map(item => item.key))
    setThreshold('70')
    setError('')
  }, [open])

  const toggleDimension = (key, checked) => {
    setDimensions(current =>
      checked ? [...new Set([...current, key])] : current.filter(item => item !== key)
    )
  }

  const handleSubmit = async () => {
    if (!datasourceId) {
      setError('请先选择数据源')
      return
    }
    if (dimensions.length === 0) {
      setError('至少选择一个评估维度')
      return
    }
    try {
      await mutation.mutateAsync({
        datasourceId,
        dimensions,
        threshold: Number(threshold) || 70,
      })
      notify.success('评估任务已入队')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建评估任务"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending} disabled={mutation.isPending}>
            启动评估
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

        <div className="space-y-2">
          <span className="block text-sm font-medium text-gray-700">评估维度</span>
          {DIMENSIONS.map(item => (
            <Checkbox
              key={item.key}
              label={item.label}
              checked={dimensions.includes(item.key)}
              onCheckedChange={checked => toggleDimension(item.key, checked === true)}
              disabled={mutation.isPending}
            />
          ))}
        </div>

        <div>
          <label
            htmlFor="evaluation-threshold"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            问题标记阈值（0–100）
          </label>
          <Input
            id="evaluation-threshold"
            type="number"
            value={threshold}
            onChange={setThreshold}
            disabled={mutation.isPending}
          />
          <p className="mt-1 text-xs text-gray-500">
            低于阈值的维度会被标记为问题；总分 &lt; 70 进入人工复核。
          </p>
        </div>
      </div>
    </Modal>
  )
}
