import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CreateCleaningModal } from './CreateCleaningModal'
import { listDataSources } from '../../api/datasources'
import { startCleaning } from '../../api/cleaning'

vi.mock('../../api/datasources', () => ({
  listDataSources: vi.fn(),
  getDataSource: vi.fn(),
  createDataSource: vi.fn(),
  updateDataSource: vi.fn(),
  deleteDataSource: vi.fn(),
  uploadDataSourceFile: vi.fn(),
}))
vi.mock('../../api/cleaning', () => ({
  startCleaning: vi.fn(),
  listCleanedData: vi.fn(),
  getCleanedData: vi.fn(),
}))

function renderModal(onClose = () => {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CreateCleaningModal open onClose={onClose} defaultDatasourceId="ds-1" />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('CreateCleaningModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listDataSources.mockResolvedValue({
      items: [
        { id: 'ds-1', name: '客服1月' },
        { id: 'ds-2', name: '销售2月' },
      ],
      pagination: { total: 2 },
    })
    startCleaning.mockResolvedValue({ task_id: 't-1' })
  })

  it('默认选中数据源并提交清洗配置', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderModal(onClose)

    await waitFor(() => expect(screen.getByRole('combobox')).toHaveTextContent('客服1月'))
    await user.click(screen.getByRole('button', { name: '启动清洗' }))

    await waitFor(() =>
      expect(startCleaning).toHaveBeenCalledWith('ds-1', {
        dataIds: undefined,
        config: { remove_duplicates: true, normalize_text: true },
      })
    )
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('关闭去重开关后提交 false', async () => {
    const user = userEvent.setup()
    renderModal()
    await waitFor(() => expect(screen.getByRole('combobox')).toHaveTextContent('客服1月'))

    await user.click(screen.getByRole('switch', { name: /去重/ }))
    await user.click(screen.getByRole('button', { name: '启动清洗' }))

    await waitFor(() =>
      expect(startCleaning).toHaveBeenCalledWith(
        'ds-1',
        expect.objectContaining({
          config: { remove_duplicates: false, normalize_text: true },
        })
      )
    )
  })

  it('已有任务运行时展示错误', async () => {
    startCleaning.mockRejectedValue({ status: 409, code: 'TASK_ALREADY_RUNNING' })
    const user = userEvent.setup()
    renderModal()
    await waitFor(() => expect(screen.getByRole('combobox')).toHaveTextContent('客服1月'))

    await user.click(screen.getByRole('button', { name: '启动清洗' }))

    expect(await screen.findByText('已有同类任务在运行，请稍后再试')).toBeInTheDocument()
  })

  it('无数据源时提供新建/管理入口，不留下空白死路', async () => {
    listDataSources.mockResolvedValue({ items: [], pagination: { total: 0 } })
    renderModal()

    expect(await screen.findByRole('alert')).toHaveTextContent('还没有可用数据源')
    expect(screen.getByRole('link', { name: '新建数据源' })).toHaveAttribute(
      'href',
      '/data-sources?action=create'
    )
    expect(screen.getByRole('link', { name: '去数据源管理' })).toHaveAttribute(
      'href',
      '/data-sources'
    )
    expect(screen.getByRole('button', { name: '启动清洗' })).toBeDisabled()
    expect(startCleaning).not.toHaveBeenCalled()
  })
})
