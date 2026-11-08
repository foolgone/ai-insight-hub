import { useEffect, useState } from 'react'
import { Modal } from '../Modal'
import { Input } from '../Input'
import { Button } from '../Button'
import {
  useCreateDatasourceType,
  useDatasourceTypesQuery,
  useDeleteDatasourceType,
  useUpdateDatasourceType,
} from '../../hooks/useDatasourceTypes'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const CONTAIN_CJK = /[\u4e00-\u9fa5]/

/** 类型字典的服务端错误文案更具体（如「内置类型不可删除」），优先展示中文原文。 */
function messageOf(error) {
  if (!error) return ''
  if (typeof error.message === 'string' && CONTAIN_CJK.test(error.message)) return error.message
  return getErrorMessage(error)
}

/**
 * 数据源类型管理（admin）：增 / 改名 / 启停 / 删。
 *
 * - code 是稳定标识，创建后不可修改（数据源按 code 关联）；
 * - 内置类型不可删除，可改名或停用；
 * - 仍被数据源使用的类型删除会被服务端拒绝（409）。
 * @param {{ open: boolean, onClose: () => void }} props
 */
export function DataSourceTypeManager({ open, onClose }) {
  const { data, isLoading } = useDatasourceTypesQuery({ includeInactive: true, enabled: open })
  const createMutation = useCreateDatasourceType()
  const updateMutation = useUpdateDatasourceType()
  const deleteMutation = useDeleteDatasourceType()

  const [label, setLabel] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editLabel, setEditLabel] = useState('')
  const [confirmingId, setConfirmingId] = useState(null)

  useEffect(() => {
    if (!open) return
    setLabel('')
    setCode('')
    setError('')
    setEditingId(null)
    setConfirmingId(null)
  }, [open])

  const items = data?.items ?? []
  const busy =
    createMutation.isPending || updateMutation.isPending || deleteMutation.isPending

  const handleCreate = async () => {
    if (!label.trim()) {
      setError('请输入类型名称')
      return
    }
    setError('')
    try {
      await createMutation.mutateAsync({
        label: label.trim(),
        code: code.trim() || undefined,
      })
      setLabel('')
      setCode('')
      notify.success('类型已新增')
    } catch (createError) {
      setError(messageOf(createError))
    }
  }

  const handleRename = async item => {
    if (!editLabel.trim()) {
      setError('类型名称不能为空')
      return
    }
    setError('')
    try {
      await updateMutation.mutateAsync({
        id: item.id,
        payload: { label: editLabel.trim() },
      })
      setEditingId(null)
      notify.success('类型已更新')
    } catch (updateError) {
      setError(messageOf(updateError))
    }
  }

  const handleToggle = async item => {
    setError('')
    try {
      await updateMutation.mutateAsync({
        id: item.id,
        payload: { is_active: !item.is_active },
      })
    } catch (toggleError) {
      setError(messageOf(toggleError))
    }
  }

  const handleDelete = async item => {
    setError('')
    try {
      await deleteMutation.mutateAsync(item.id)
      setConfirmingId(null)
      notify.success('类型已删除')
    } catch (deleteError) {
      setConfirmingId(null)
      setError(messageOf(deleteError))
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="数据源类型管理" size="md">
      <p className="mb-4 text-sm text-gray-600">
        类型是全局字典：改名只影响展示，历史数据仍按标识关联。
        停用后不再出现在新建下拉中；内置类型不可删除。
      </p>

      {error ? (
        <div
          role="alert"
          className="mb-3 border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
        >
          {error}
        </div>
      ) : null}

      <div className="mb-5 grid grid-cols-1 items-start gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <Input
          value={label}
          onChange={setLabel}
          placeholder="类型名称，如：售后"
          aria-label="新类型名称"
          disabled={busy}
        />
        <Input
          value={code}
          onChange={setCode}
          placeholder="标识（可选，英文）"
          aria-label="新类型标识"
          disabled={busy}
        />
        <Button onClick={handleCreate} loading={createMutation.isPending} disabled={busy}>
          新增
        </Button>
      </div>

      {isLoading ? (
        <p className="py-6 text-center text-sm text-gray-500">加载中…</p>
      ) : items.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">还没有任何类型</p>
      ) : (
        <ul className="divide-y divide-gray-100 border-y border-gray-100">
          {items.map(item => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                {editingId === item.id ? (
                  <div className="flex items-center gap-2">
                    <Input
                      value={editLabel}
                      onChange={setEditLabel}
                      aria-label={`重命名 ${item.label}`}
                      className="w-40"
                      disabled={busy}
                    />
                    <Button size="sm" loading={updateMutation.isPending} onClick={() => handleRename(item)}>
                      保存
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                      取消
                    </Button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-gray-900">{item.label}</span>
                    <span className="font-mono text-[11px] text-gray-400">{item.code}</span>
                    {item.is_system ? (
                      <span className="bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                        默认
                      </span>
                    ) : null}
                    {item.is_active ? null : (
                      <span className="bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
                        已停用
                      </span>
                    )}
                    <span className="font-mono text-[11px] text-gray-500">
                      {item.usage_count} 个数据源
                    </span>
                  </div>
                )}
              </div>

              {editingId === item.id ? null : confirmingId === item.id ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-error-600">确认删除？</span>
                  <Button
                    size="sm"
                    variant="danger"
                    loading={deleteMutation.isPending}
                    onClick={() => handleDelete(item)}
                  >
                    确认
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmingId(null)}>
                    取消
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`编辑 ${item.label}`}
                    onClick={() => {
                      setEditingId(item.id)
                      setEditLabel(item.label)
                      setConfirmingId(null)
                    }}
                  >
                    编辑
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`${item.is_active ? '停用' : '启用'} ${item.label}`}
                    disabled={busy}
                    onClick={() => handleToggle(item)}
                  >
                    {item.is_active ? '停用' : '启用'}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`删除 ${item.label}`}
                    disabled={busy}
                    onClick={() => {
                      setConfirmingId(item.id)
                      setEditingId(null)
                    }}
                  >
                    删除
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}
