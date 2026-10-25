import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { useExtractKnowledge } from '../../hooks/useKnowledge'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

/**
 * 触发知识提取（F-403）：参数 min_frequency / similarity_threshold / max_faq_count（202）。
 * @param {{ open: boolean, onClose: () => void, datasourceId: string|null }} props
 */
export function ExtractKnowledgeModal({ open, onClose, datasourceId }) {
  const mutation = useExtractKnowledge()
  const [minFrequency, setMinFrequency] = useState('3')
  const [similarityThreshold, setSimilarityThreshold] = useState('0.85')
  const [maxFaqCount, setMaxFaqCount] = useState('100')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setMinFrequency('3')
    setSimilarityThreshold('0.85')
    setMaxFaqCount('100')
    setError('')
  }, [open])

  const handleSubmit = async () => {
    if (!datasourceId) {
      setError('请先选择数据源')
      return
    }
    try {
      await mutation.mutateAsync({
        datasourceId,
        payload: {
          min_frequency: Number(minFrequency) || 3,
          similarity_threshold: Number(similarityThreshold) || 0.85,
          max_faq_count: Number(maxFaqCount) || 100,
        },
      })
      notify.success('知识提取任务已入队')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="提取知识"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending} disabled={mutation.isPending}>
            启动提取
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
        <p className="text-sm text-gray-600">
          从清洗结果中聚类高频问题并提取 FAQ；任务异步执行，可在「数据清洗」页查看进度。
        </p>

        <div>
          <label htmlFor="extract-min" className="mb-1 block text-sm font-medium text-gray-700">
            最小出现次数（min_frequency）
          </label>
          <Input
            id="extract-min"
            type="number"
            value={minFrequency}
            onChange={setMinFrequency}
            disabled={mutation.isPending}
          />
        </div>
        <div>
          <label
            htmlFor="extract-similarity"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            相似度阈值（similarity_threshold，0–1）
          </label>
          <Input
            id="extract-similarity"
            type="number"
            value={similarityThreshold}
            onChange={setSimilarityThreshold}
            disabled={mutation.isPending}
          />
        </div>
        <div>
          <label htmlFor="extract-max" className="mb-1 block text-sm font-medium text-gray-700">
            最多提取条数（max_faq_count）
          </label>
          <Input
            id="extract-max"
            type="number"
            value={maxFaqCount}
            onChange={setMaxFaqCount}
            disabled={mutation.isPending}
          />
        </div>
      </div>
    </Modal>
  )
}
