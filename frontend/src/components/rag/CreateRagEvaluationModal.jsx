import { useEffect, useMemo, useState } from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { Select } from '../Select'
import { getErrorMessage } from '../../lib/errorMessages'
import {
  useCreateRagEvaluation,
  useDatasetVersionsQuery,
  useDatasetsQuery,
} from '../../hooks/useRagEvaluations'

const MODE_OPTIONS = [
  { label: 'query：执行检索 + 生成答案', value: 'query' },
  { label: 'retrieve：只执行检索', value: 'retrieve' },
]

const ADAPTER_OPTIONS = [
  { label: 'mock（本地模拟，验证链路）', value: 'mock' },
  { label: 'weknora（真实知识库）', value: 'weknora' },
]

/**
 * 新建 RAG 评测 Run。
 * P0 只暴露必要字段：数据集版本 / 模式 / 适配器 / 条数上限。
 */
export function CreateRagEvaluationModal({ open, onClose, onCreated }) {
  const [datasetId, setDatasetId] = useState('')
  const [versionId, setVersionId] = useState('')
  const [mode, setMode] = useState('query')
  const [adapter, setAdapter] = useState('mock')
  const [limit, setLimit] = useState('20')
  const [submitError, setSubmitError] = useState('')

  const datasetsQuery = useDatasetsQuery(open)
  const versionsQuery = useDatasetVersionsQuery(datasetId)
  const createMutation = useCreateRagEvaluation()

  useEffect(() => {
    if (!open) {
      setDatasetId('')
      setVersionId('')
      setMode('query')
      setAdapter('mock')
      setLimit('20')
      setSubmitError('')
    }
  }, [open])

  useEffect(() => {
    setVersionId('')
  }, [datasetId])

  const datasetOptions = useMemo(
    () =>
      (datasetsQuery.data?.items || []).map(item => ({
        label: item.name,
        value: item.id,
      })),
    [datasetsQuery.data]
  )

  const versionOptions = useMemo(
    () =>
      (versionsQuery.data?.items || []).map(item => ({
        label: `v${item.version} · ${item.status} · ${item.item_count} 条`,
        value: item.id,
      })),
    [versionsQuery.data]
  )

  const handleSubmit = async () => {
    setSubmitError('')
    if (!versionId) {
      setSubmitError('请选择数据集版本')
      return
    }
    const parsedLimit = Number(limit)
    if (!Number.isFinite(parsedLimit) || parsedLimit < 1 || parsedLimit > 200) {
      setSubmitError('条数上限需在 1–200 之间')
      return
    }
    try {
      const created = await createMutation.mutateAsync({
        dataset_version_id: versionId,
        execution_mode: mode,
        adapter,
        split: 'test',
        limit: Math.trunc(parsedLimit),
      })
      onCreated?.(created)
      onClose?.()
    } catch (error) {
      setSubmitError(getErrorMessage(error))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建 RAG 评测"
      size="md"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={createMutation.isPending} disabled={!versionId}>
            创建并运行
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="rag-dataset">
            数据集
          </label>
          <Select
            options={datasetOptions}
            value={datasetId}
            onChange={setDatasetId}
            placeholder={datasetsQuery.isLoading ? '加载数据集中…' : '选择数据集'}
            searchable
            disabled={datasetsQuery.isLoading}
            ariaLabel="数据集"
          />
          {!datasetsQuery.isLoading && !datasetOptions.length ? (
            <p className="mt-1 text-xs text-gray-500">
              还没有 QA 数据集。先通过 /qa-datasets API 导入数据后，再回来创建评测。
            </p>
          ) : null}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="rag-version">
            数据集版本
          </label>
          <Select
            options={versionOptions}
            value={versionId}
            onChange={setVersionId}
            placeholder={
              !datasetId ? '先选择数据集' : versionsQuery.isLoading ? '加载版本中…' : '选择版本'
            }
            disabled={!datasetId || versionsQuery.isLoading}
            ariaLabel="数据集版本"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="rag-mode">
              执行模式
            </label>
            <Select options={MODE_OPTIONS} value={mode} onChange={setMode} ariaLabel="执行模式" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="rag-adapter">
              RAG 适配器
            </label>
            <Select
              options={ADAPTER_OPTIONS}
              value={adapter}
              onChange={setAdapter}
              ariaLabel="RAG 适配器"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="rag-limit">
            条数上限（1–200）
          </label>
          <Input id="rag-limit" type="number" value={limit} onChange={setLimit} placeholder="20" />
        </div>

        {submitError ? (
          <p role="alert" className="text-sm text-error-700">
            {submitError}
          </p>
        ) : null}
      </div>
    </Modal>
  )
}
