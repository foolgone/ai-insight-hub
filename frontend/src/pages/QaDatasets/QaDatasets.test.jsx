import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QaDatasets from './index'
import {
  createQaDataset,
  createQaDatasetVersion,
  deleteQaDatasetItem,
  getQaDataset,
  getQaDatasetStats,
  importQaDatasetItems,
  listQaDatasetItems,
  listQaDatasets,
  publishQaDatasetVersion,
  updateQaDatasetItem,
} from '../../api/qaDatasets'
import { useAuthStore } from '../../stores/authStore'

vi.mock('../../api/qaDatasets', () => ({
  listQaDatasets: vi.fn(),
  getQaDataset: vi.fn(),
  createQaDataset: vi.fn(),
  createQaDatasetVersion: vi.fn(),
  importQaDatasetItems: vi.fn(),
  publishQaDatasetVersion: vi.fn(),
  listQaDatasetItems: vi.fn(),
  updateQaDatasetItem: vi.fn(),
  deleteQaDatasetItem: vi.fn(),
  getQaDatasetStats: vi.fn(),
}))

const DATASET = {
  id: 'ds-a',
  name: '售后政策评测集',
  description: '退款/发货/发票',
  source_type: 'mixed',
  created_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-27T09:00:00Z',
}

const VERSION_DRAFT = {
  id: 'v2',
  dataset_id: 'ds-a',
  version: 2,
  status: 'draft',
  item_count: 2,
  checksum: null,
  note: '补充退款时效',
  published_at: null,
  created_at: '2026-11-27T09:00:00Z',
}

const VERSION_PUBLISHED = {
  id: 'v1',
  dataset_id: 'ds-a',
  version: 1,
  status: 'published',
  item_count: 2,
  checksum: 'abc',
  note: '初始版本',
  published_at: '2026-11-26T09:00:00Z',
  created_at: '2026-11-25T09:00:00Z',
}

const DETAIL = { ...DATASET, versions: [VERSION_DRAFT, VERSION_PUBLISHED] }

const STATS = {
  dataset_id: 'ds-a',
  version_id: 'v2',
  item_count: 2,
  split_counts: { train: 0, valid: 0, test: 2 },
  category_counts: { 售后: 2 },
  evidence: { with_evidence: 1, without_evidence: 1, coverage_rate: 0.5 },
}

const ITEMS = {
  items: [
    {
      id: 'i1',
      item_key: 'Q1',
      query: '退款多久到账？',
      gold_answer: '3-5 个工作日',
      gold_evidence: [],
      category: '售后',
      difficulty: 'easy',
      source: null,
      split: 'test',
      metadata: {},
      created_at: '2026-11-27T09:00:00Z',
    },
  ],
  pagination: { page: 1, limit: 10, total: 1, pages: 1 },
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <QaDatasets />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('QaDatasetsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({ user: { id: 'u1', role: 'tenant_admin', name: 'T' } })
    listQaDatasets.mockResolvedValue({
      items: [DATASET],
      pagination: { page: 1, limit: 20, total: 1, pages: 1 },
    })
    getQaDataset.mockResolvedValue(DETAIL)
    getQaDatasetStats.mockResolvedValue(STATS)
    listQaDatasetItems.mockResolvedValue(ITEMS)
  })

  afterEach(() => {
    useAuthStore.setState({ user: null })
  })

  it('展示数据集、版本和条目，draft 可导入/发布/编辑', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'QA 数据集' })).toBeInTheDocument()
    expect(await screen.findByText('售后政策评测集')).toBeInTheDocument()
    expect(await screen.findByText('v2')).toBeInTheDocument()
    expect(await screen.findByText('退款多久到账？')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '导入 JSON' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '发布版本' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '编辑 Q1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '删除 Q1' })).toBeInTheDocument()
  })

  it('空列表展示页面内 CTA，并可创建数据集', async () => {
    const user = userEvent.setup()
    listQaDatasets.mockResolvedValue({
      items: [],
      pagination: { page: 1, limit: 20, total: 0, pages: 0 },
    })
    createQaDataset.mockResolvedValue({ ...DATASET, id: 'ds-new', name: '新数据集' })

    renderPage()

    expect(await screen.findByText('还没有 QA 数据集')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: '新建数据集' })[0])
    expect(await screen.findByRole('dialog', { name: '新建 QA 数据集' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('数据集名称'), '新数据集')
    await user.click(screen.getByRole('button', { name: '创建数据集' }))

    await waitFor(() =>
      expect(createQaDataset).toHaveBeenCalledWith({
        name: '新数据集',
        description: null,
        source_type: 'mixed',
      })
    )
  })

  it('从旧版本复制时提交 from_version_id', async () => {
    const user = userEvent.setup()
    createQaDatasetVersion.mockResolvedValue({
      ...VERSION_DRAFT,
      id: 'v3',
      version: 3,
      note: null,
    })
    renderPage()
    await screen.findByText('退款多久到账？')

    await user.click(screen.getByRole('button', { name: '新建版本' }))
    expect(await screen.findByRole('dialog', { name: '新建草稿版本' })).toBeInTheDocument()
    await user.click(screen.getByRole('combobox', { name: '复制自版本' }))
    await user.click(screen.getByRole('option', { name: /v1 · 已发布 · 2 条/ }))
    await user.click(screen.getByRole('button', { name: '创建草稿' }))

    await waitFor(() =>
      expect(createQaDatasetVersion).toHaveBeenCalledWith('ds-a', {
        note: null,
        from_version_id: 'v1',
      })
    )
  })

  it('导入 JSON 解析失败不提交，后端校验错误显示行号', async () => {
    const user = userEvent.setup()
    importQaDatasetItems.mockRejectedValue({
      code: 'QA_DATASET_IMPORT_INVALID',
      details: {
        errors: [{ index: 2, field: 'item_key', message: '版本内已存在：Q1' }],
      },
    })
    renderPage()
    await screen.findByText('退款多久到账？')

    await user.click(screen.getByRole('button', { name: '导入 JSON' }))
    const textarea = await screen.findByLabelText('JSON 条目')
    await user.click(textarea)
    await user.paste('{bad json')
    await user.click(screen.getByRole('button', { name: '校验并导入' }))
    expect(await screen.findByText(/JSON 解析失败/)).toBeInTheDocument()
    expect(importQaDatasetItems).not.toHaveBeenCalled()

    await user.clear(textarea)
    await user.click(textarea)
    await user.paste('[{"item_key":"Q1","query":"q"}]')
    await user.click(screen.getByRole('button', { name: '校验并导入' }))

    expect(await screen.findByText('版本内已存在：Q1')).toBeInTheDocument()
    expect(screen.getByText('item_key')).toBeInTheDocument()
    expect(importQaDatasetItems).toHaveBeenCalledWith('ds-a', 'v2', [
      { item_key: 'Q1', query: 'q' },
    ])
  })

  it('发布版本需二次确认并调用发布接口', async () => {
    const user = userEvent.setup()
    publishQaDatasetVersion.mockResolvedValue({
      ...VERSION_DRAFT,
      status: 'published',
      published_at: '2026-11-27T10:00:00Z',
    })
    renderPage()
    await screen.findByText('退款多久到账？')

    await user.click(screen.getByRole('button', { name: '发布版本' }))
    expect(await screen.findByRole('dialog', { name: '发布版本 v2' })).toBeInTheDocument()
    expect(screen.getByText(/发布后不可撤销/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认发布' }))

    await waitFor(() => expect(publishQaDatasetVersion).toHaveBeenCalledWith('ds-a', 'v2'))
  })

  it('已发布版本只读：不显示导入/发布/编辑', async () => {
    getQaDataset.mockResolvedValue({ ...DATASET, versions: [VERSION_PUBLISHED] })
    renderPage()

    expect(await screen.findByText('已发布 · 不可变')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '导入 JSON' })).toBeNull()
    expect(screen.queryByRole('button', { name: '发布版本' })).toBeNull()
    expect(screen.queryByRole('button', { name: '编辑 Q1' })).toBeNull()
    expect(await screen.findByText('只读')).toBeInTheDocument()
  })

  it('draft 条目可编辑并提交安全字段', async () => {
    const user = userEvent.setup()
    updateQaDatasetItem.mockResolvedValue({
      ...ITEMS.items[0],
      query: '退款多久到账？更新版',
    })
    renderPage()
    await screen.findByText('退款多久到账？')

    await user.click(screen.getByRole('button', { name: '编辑 Q1' }))
    expect(await screen.findByRole('dialog', { name: '编辑条目 · Q1' })).toBeInTheDocument()
    const queryInput = screen.getByLabelText('Query')
    await user.clear(queryInput)
    await user.type(queryInput, '退款多久到账？更新版')
    await user.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() =>
      expect(updateQaDatasetItem).toHaveBeenCalledWith(
        'ds-a',
        'v2',
        'i1',
        expect.objectContaining({
          query: '退款多久到账？更新版',
          split: 'test',
        })
      )
    )
  })

  it('导入成功后刷新统计与条目', async () => {
    const user = userEvent.setup()
    importQaDatasetItems.mockResolvedValue({ imported: 1, version_item_count: 3 })
    renderPage()
    await screen.findByText('退款多久到账？')

    await user.click(screen.getByRole('button', { name: '导入 JSON' }))
    const textarea = await screen.findByLabelText('JSON 条目')
    await user.click(textarea)
    await user.paste('[{"item_key":"Q2","query":"发货多久？"}]')
    await user.click(screen.getByRole('button', { name: '校验并导入' }))

    await waitFor(() =>
      expect(importQaDatasetItems).toHaveBeenCalledWith('ds-a', 'v2', [
        { item_key: 'Q2', query: '发货多久？' },
      ])
    )
  })

  it('删除 draft 条目需确认并调用删除接口', async () => {
    const user = userEvent.setup()
    deleteQaDatasetItem.mockResolvedValue(undefined)
    renderPage()
    await screen.findByText('退款多久到账？')

    await user.click(screen.getByRole('button', { name: '删除 Q1' }))
    await user.click(await screen.findByRole('button', { name: '删除' }))

    await waitFor(() => expect(deleteQaDatasetItem).toHaveBeenCalledWith('ds-a', 'v2', 'i1'))
  })

  it('搜索按名称调用列表接口', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('售后政策评测集')

    await user.type(screen.getByLabelText('搜索数据集名称'), '退款')
    await user.click(screen.getByRole('button', { name: '搜索' }))

    await waitFor(() =>
      expect(listQaDatasets).toHaveBeenLastCalledWith(
        expect.objectContaining({ keyword: '退款', page: 1 })
      )
    )
  })

  it('viewer 只读：不显示创建/导入/编辑/删除', async () => {
    useAuthStore.setState({ user: { id: 'u2', role: 'viewer', name: 'V' } })
    renderPage()

    expect(await screen.findByText('售后政策评测集')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '新建数据集' })).toBeNull()
    expect(screen.queryByRole('button', { name: '导入 JSON' })).toBeNull()
    expect(screen.queryByRole('button', { name: '编辑 Q1' })).toBeNull()
    expect(screen.queryByRole('button', { name: '删除 Q1' })).toBeNull()
  })
})
