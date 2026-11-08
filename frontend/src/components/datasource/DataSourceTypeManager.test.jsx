import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DataSourceTypeManager } from './DataSourceTypeManager'

let items = []

const createMutation = { mutateAsync: vi.fn(), isPending: false }
const updateMutation = { mutateAsync: vi.fn(), isPending: false }
const deleteMutation = { mutateAsync: vi.fn(), isPending: false }

vi.mock('../../hooks/useDatasourceTypes', () => ({
  useDatasourceTypesQuery: () => ({ data: { items }, isLoading: false }),
  useCreateDatasourceType: () => createMutation,
  useUpdateDatasourceType: () => updateMutation,
  useDeleteDatasourceType: () => deleteMutation,
}))

const SYSTEM_TYPE = {
  id: 't-1',
  code: 'customer_service',
  label: '客服对话',
  sort_order: 10,
  is_system: true,
  is_active: true,
  usage_count: 3,
}

const CUSTOM_TYPE = {
  id: 't-2',
  code: 'after_sales',
  label: '售后',
  sort_order: 40,
  is_system: false,
  is_active: true,
  usage_count: 0,
}

describe('DataSourceTypeManager', () => {
  beforeEach(() => {
    items = [SYSTEM_TYPE, CUSTOM_TYPE]
    vi.clearAllMocks()
    createMutation.mutateAsync.mockResolvedValue({})
    updateMutation.mutateAsync.mockResolvedValue({})
    deleteMutation.mutateAsync.mockResolvedValue(undefined)
  })

  it('展示类型、标识、默认标记与使用量', () => {
    render(<DataSourceTypeManager open onClose={() => {}} />)

    expect(screen.getByText('客服对话')).toBeInTheDocument()
    expect(screen.getByText('customer_service')).toBeInTheDocument()
    expect(screen.getByText('默认')).toBeInTheDocument()
    expect(screen.getByText('3 个数据源')).toBeInTheDocument()
    expect(screen.getByText('售后')).toBeInTheDocument()
  })

  it('新增类型调用接口并清空输入', async () => {
    const user = userEvent.setup()
    render(<DataSourceTypeManager open onClose={() => {}} />)

    await user.type(screen.getByLabelText('新类型名称'), '售后')
    await user.type(screen.getByLabelText('新类型标识'), 'after_sales')
    await user.click(screen.getByRole('button', { name: '新增' }))

    await waitFor(() =>
      expect(createMutation.mutateAsync).toHaveBeenCalledWith({
        label: '售后',
        code: 'after_sales',
      })
    )
    expect(screen.getByLabelText('新类型名称')).toHaveValue('')
  })

  it('名称为空时提示且不调用接口', async () => {
    const user = userEvent.setup()
    render(<DataSourceTypeManager open onClose={() => {}} />)

    await user.click(screen.getByRole('button', { name: '新增' }))

    expect(screen.getByText('请输入类型名称')).toBeInTheDocument()
    expect(createMutation.mutateAsync).not.toHaveBeenCalled()
  })

  it('删除需要二次确认', async () => {
    const user = userEvent.setup()
    render(<DataSourceTypeManager open onClose={() => {}} />)

    await user.click(screen.getByRole('button', { name: '删除 售后' }))
    expect(deleteMutation.mutateAsync).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '确认' }))

    await waitFor(() => expect(deleteMutation.mutateAsync).toHaveBeenCalledWith('t-2'))
  })

  it('删除被拒绝时展示服务端中文原因', async () => {
    deleteMutation.mutateAsync.mockRejectedValue({
      code: 'DATASOURCE_TYPE_INVALID',
      message: '内置类型不可删除，可改为停用',
    })
    const user = userEvent.setup()
    render(<DataSourceTypeManager open onClose={() => {}} />)

    await user.click(screen.getByRole('button', { name: '删除 客服对话' }))
    await user.click(screen.getByRole('button', { name: '确认' }))

    expect(await screen.findByText('内置类型不可删除，可改为停用')).toBeInTheDocument()
  })

  it('停用类型调用更新接口', async () => {
    const user = userEvent.setup()
    render(<DataSourceTypeManager open onClose={() => {}} />)

    await user.click(screen.getByRole('button', { name: '停用 售后' }))

    await waitFor(() =>
      expect(updateMutation.mutateAsync).toHaveBeenCalledWith({
        id: 't-2',
        payload: { is_active: false },
      })
    )
  })
})
