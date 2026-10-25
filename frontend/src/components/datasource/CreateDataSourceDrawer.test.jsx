import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CreateDataSourceDrawer } from './CreateDataSourceDrawer'
import { createDataSource, uploadDataSourceFile } from '../../api/datasources'

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))

describe('CreateDataSourceDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createDataSource.mockResolvedValue({ id: 'ds-1', name: '客服1月' })
    uploadDataSourceFile.mockResolvedValue({ task_id: 't-1', status: 'pending' })
  })

  it('步骤 1 校验名称必填', async () => {
    const user = userEvent.setup()
    render(<CreateDataSourceDrawer open onClose={() => {}} />)

    await user.click(screen.getByRole('button', { name: '下一步' }))

    expect(screen.getByText('请输入数据源名称')).toBeInTheDocument()
  })

  it('填写名称后进入步骤 2', async () => {
    const user = userEvent.setup()
    render(<CreateDataSourceDrawer open onClose={() => {}} />)

    await user.type(screen.getByLabelText(/名称/), '客服1月')
    await user.click(screen.getByRole('button', { name: '下一步' }))

    expect(screen.getByLabelText(/数据文件/)).toBeInTheDocument()
  })

  it('步骤 2 未选择文件时提示', async () => {
    const user = userEvent.setup()
    render(<CreateDataSourceDrawer open onClose={() => {}} />)

    await user.type(screen.getByLabelText(/名称/), '客服1月')
    await user.click(screen.getByRole('button', { name: '下一步' }))
    await user.click(screen.getByRole('button', { name: '创建并上传' }))

    expect(screen.getByText('请选择要上传的文件')).toBeInTheDocument()
    expect(createDataSource).not.toHaveBeenCalled()
  })

  it('创建成功并上传后回调 onSuccess', async () => {
    const onSuccess = vi.fn()
    const user = userEvent.setup()
    render(<CreateDataSourceDrawer open onClose={() => {}} onSuccess={onSuccess} />)

    await user.type(screen.getByLabelText(/名称/), '客服1月')
    await user.click(screen.getByRole('button', { name: '下一步' }))
    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    await user.upload(screen.getByLabelText(/数据文件/), file)
    await user.click(screen.getByRole('button', { name: '创建并上传' }))

    await waitFor(() =>
      expect(createDataSource).toHaveBeenCalledWith({
        name: '客服1月',
        type: 'customer_service',
      })
    )
    expect(uploadDataSourceFile).toHaveBeenCalledWith('ds-1', file)
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith({ id: 'ds-1', name: '客服1月' }))
  })

  it('取消关闭 Drawer', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<CreateDataSourceDrawer open onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: '取消' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('创建失败展示错误文案', async () => {
    createDataSource.mockRejectedValue({ status: 429, code: 'DATASOURCE_QUOTA_EXCEEDED' })
    const user = userEvent.setup()
    render(<CreateDataSourceDrawer open onClose={() => {}} />)

    await user.type(screen.getByLabelText(/名称/), '客服1月')
    await user.click(screen.getByRole('button', { name: '下一步' }))
    await user.upload(
      screen.getByLabelText(/数据文件/),
      new File(['a,b'], 'data.csv', { type: 'text/csv' })
    )
    await user.click(screen.getByRole('button', { name: '创建并上传' }))

    expect(await screen.findByText('数据源数量已达配额上限')).toBeInTheDocument()
  })
})
