import { useEffect, useState } from 'react'
import { Button } from '../Button'
import { Input } from '../Input'
import { Modal } from '../Modal'
import { Select } from '../Select'
import { useUpdateDataSource } from '../../hooks/useDataSources'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const TYPE_OPTIONS = [
  { label: '客服对话', value: 'customer_service' },
  { label: '销售', value: 'sales' },
  { label: '支持', value: 'support' },
  { label: '其他', value: 'other' },
]

/**
 * 编辑数据源（F-204）：PATCH 局部更新名称/描述/类型。
 * @param {{ datasource: Object|null, open: boolean, onClose: () => void }} props
 */
export function EditDataSourceModal({ datasource, open, onClose }) {
  const mutation = useUpdateDataSource()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState('other')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !datasource) return
    setName(datasource.name || '')
    setDescription(datasource.description || '')
    setType(datasource.type || 'other')
    setError('')
  }, [open, datasource])

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('请输入数据源名称')
      return
    }
    try {
      await mutation.mutateAsync({
        id: datasource.id,
        payload: {
          name: name.trim(),
          description: description.trim() || undefined,
          type,
        },
      })
      notify.success('数据源已更新')
      onClose()
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="编辑数据源"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            取消
          </Button>
          <Button onClick={handleSubmit} loading={mutation.isPending} disabled={mutation.isPending}>
            保存
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
          <label
            htmlFor="edit-datasource-name"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            名称 <span className="text-error-500">*</span>
          </label>
          <Input
            id="edit-datasource-name"
            value={name}
            onChange={setName}
            disabled={mutation.isPending}
          />
        </div>
        <div>
          <label
            htmlFor="edit-datasource-description"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            描述
          </label>
          <Input
            id="edit-datasource-description"
            value={description}
            onChange={setDescription}
            disabled={mutation.isPending}
          />
        </div>
        <div>
          <span className="mb-1 block text-sm font-medium text-gray-700">类型</span>
          <Select
            options={TYPE_OPTIONS}
            value={type}
            onChange={setType}
            disabled={mutation.isPending}
          />
        </div>
      </div>
    </Modal>
  )
}
