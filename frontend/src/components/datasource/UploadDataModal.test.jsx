import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { UploadDataModal } from './UploadDataModal'
import { uploadDataSourceFile } from '../../api/datasources'

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
      <UploadDataModal datasource={DATASOURCE} open onClose={onClose} />
    </QueryClientProvider>
  )
}

describe('UploadDataModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    uploadDataSourceFile.mockResolvedValue({ task_id: 't-1', status: 'pending' })
  })

  it('未选择文件时提示', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('button', { name: /上传/ }))

    expect(screen.getByText('请选择要上传的文件')).toBeInTheDocument()
    expect(uploadDataSourceFile).not.toHaveBeenCalled()
  })

  it('选择文件后上传成功并关闭', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderModal(onClose)

    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    await user.upload(screen.getByLabelText('数据文件'), file)
    await user.click(screen.getByRole('button', { name: /上传/ }))

    await waitFor(() => expect(uploadDataSourceFile).toHaveBeenCalledWith('ds-1', file))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
