import { useEffect, useMemo, useState } from 'react'
import { Button } from '../Button'
import { Modal } from '../Modal'
import { Select } from '../Select'
import { Switch } from '../Switch'
import { useDataSourcesQuery } from '../../hooks/useDataSources'
import { useStartCleaning } from '../../hooks/useCleaning'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

/**
 * 新建清洗任务（F-207）：选择数据源 + 去重/文本标准化开关（D-F09）。
 * @param {{ open: boolean, onClose: () => void, defaultDatasourceId?: string|null }} props
 */
export function CreateCleaningModal({ open, onClose, defaultDatasourceId = null }) {
  const { data } = useDataSourcesQuery({ page: 1, limit: 100, sort: '-created_at' })
  const mutation = useStartCleaning()

  const [datasourceId, setDatasourceId] = useState('')
  const [removeDuplicates, setRemoveDuplicates] = useState(true)
  const [normalizeText, setNormalizeText] = useState(true)
  const [error, setError] = useState('')

  const datasourceOptions = useMemo(
    () => (data?.items || []).map(item => ({ label: item.name, value: item.id })),
    [data]
  )

  useEffect(() => {
    if (!open) return
    setError('')
    const preferred = datasourceOptions.some(item => item.value === defaultDatasourceId)
      ? defaultDatasourceId
      : datasourceOptions[0]?.value || ''
    setDatasourceId(preferred)
    setRemoveDuplicates(true)
    setNormalizeText(true)
  }, [open, defaultDatasourceId, datasourceOptions])

  const handleSubmit = async () => {
    if (!datasourceId) {
      setError('请选择数据源')
      return
    }
    try {
      await mutation.mutateAsync({
        datasourceId,
        config: { remove_duplicates: removeDuplicates, normalize_text: normalizeText },
      })
      notify.success('清洗任务已入队')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建清洗任务"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending} disabled={mutation.isPending}>
            启动清洗
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
          <span className="mb-1 block text-sm font-medium text-gray-700">数据源</span>
          <Select
            options={datasourceOptions}
            value={datasourceId}
            onChange={setDatasourceId}
            placeholder="请选择数据源"
            disabled={mutation.isPending}
          />
        </div>

        <div className="space-y-3 rounded border border-gray-200 p-3">
          <Switch
            label="去重（remove_duplicates）"
            checked={removeDuplicates}
            onCheckedChange={setRemoveDuplicates}
            disabled={mutation.isPending}
          />
          <Switch
            label="文本标准化（normalize_text）"
            checked={normalizeText}
            onCheckedChange={setNormalizeText}
            disabled={mutation.isPending}
          />
          <p className="text-xs text-gray-500">
            敏感信息脱敏与格式标准化由固定管线执行；清洗范围默认为该数据源下全部待处理数据。
          </p>
        </div>
      </div>
    </Modal>
  )
}
