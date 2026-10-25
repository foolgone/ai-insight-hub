import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DeleteDataSourceModal } from './DeleteDataSourceModal'
import { deleteDataSource } from '../../api/datasources'

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

const DATASOURCE = { id: 'ds-1', name: '客服1月' }

function renderModal(onClose = () => {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <DeleteDataSourceModal datasource={DATASOURCE} open onClose={onClose} />
    </QueryClientProvider>
  )
}

describe('DeleteDataSourceModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    deleteDataSource.mockResolvedValue({ message: 'ok', deleted_records: 1 })
  })

  it('默认软删（force=false）', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderModal(onClose)

    await user.click(screen.getByRole('button', { name: '确认删除' }))

    await waitFor(() => expect(deleteDataSource).toHaveBeenCalledWith('ds-1', { force: false }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('勾选物理删除后 force=true', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('checkbox', { name: /物理删除/ }))
    await user.click(screen.getByRole('button', { name: '确认删除' }))

    await waitFor(() => expect(deleteDataSource).toHaveBeenCalledWith('ds-1', { force: true }))
  })
})
