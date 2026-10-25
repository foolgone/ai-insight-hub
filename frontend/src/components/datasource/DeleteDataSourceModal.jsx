import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Checkbox } from '../Checkbox'
import { Modal } from '../Modal'
import { useDeleteDataSource } from '../../hooks/useDataSources'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

/**
 * 删除数据源（F-204）：默认软删；勾选 force 后物理删除且不可恢复。
 * @param {{ datasource: Object|null, open: boolean, onClose: () => void, canForce?: boolean }} props
 */
export function DeleteDataSourceModal({ datasource, open, onClose, canForce = true }) {
  const mutation = useDeleteDataSource()
  const [force, setForce] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setForce(false)
    setError('')
  }, [open])

  const handleSubmit = async () => {
    try {
      await mutation.mutateAsync({ id: datasource.id, force })
      notify.success(force ? '数据源及关联数据已物理删除' : '数据源已删除')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="删除数据源"
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button
            variant="danger"
            onClick={handleSubmit}
            loading={mutation.isPending}
            disabled={mutation.isPending}
          >
            确认删除
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
        <p className="text-sm text-gray-700">
          确认删除数据源「<span className="font-medium">{datasource?.name || ''}</span>」？
          默认执行软删除，数据不会立即从数据库移除。
        </p>
        {canForce ? (
          <Checkbox
            label="同时物理删除关联数据（不可恢复）"
            checked={force}
            onCheckedChange={checked => setForce(checked === true)}
            disabled={mutation.isPending}
          />
        ) : null}
      </div>
    </Modal>
  )
}
