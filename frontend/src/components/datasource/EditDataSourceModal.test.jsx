import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EditDataSourceModal } from './EditDataSourceModal'
import { updateDataSource } from '../../api/datasources'

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

const DATASOURCE = {
  id: 'ds-1',
  name: '客服1月',
  description: '批次',
  type: 'customer_service',
}

function renderModal(onClose = () => {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <EditDataSourceModal datasource={DATASOURCE} open onClose={onClose} />
    </QueryClientProvider>
  )
}

describe('EditDataSourceModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateDataSource.mockResolvedValue({ id: 'ds-1' })
  })

  it('回显名称/描述', () => {
    renderModal()

    expect(screen.getByLabelText(/名称/)).toHaveValue('客服1月')
    expect(screen.getByLabelText('描述')).toHaveValue('批次')
  })

  it('名称为空时阻止提交', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.clear(screen.getByLabelText(/名称/))
    await user.click(screen.getByRole('button', { name: '保存' }))

    expect(screen.getByText('请输入数据源名称')).toBeInTheDocument()
    expect(updateDataSource).not.toHaveBeenCalled()
  })

  it('提交 PATCH 并关闭', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderModal(onClose)

    await user.clear(screen.getByLabelText(/名称/))
    await user.type(screen.getByLabelText(/名称/), '客服2月')
    await user.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() =>
      expect(updateDataSource).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({ name: '客服2月', type: 'customer_service' })
      )
    )
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
