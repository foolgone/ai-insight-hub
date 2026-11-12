import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RawDataPanel } from './RawDataPanel'
import { listRawData, structureRawData } from '../../api/datasources'

vi.mock('../../api/datasources', () => ({
  listRawData: vi.fn(),
  structureRawData: vi.fn(),
}))

const MEDIA_PENDING = {
  id: 'raw-1',
  filename: '众联一面.mp3',
  size: 56753537,
  format: 'media',
  duration: 2364.7,
  channels: 1,
  channel_mode: 'mono',
  asr_status: 'completed',
  structure_status: 'pending',
  structure_kind: null,
  qa_count: 0,
  partial: false,
  error: null,
  status: 'completed',
  created_at: '2026-11-11T12:20:30Z',
}

const MEDIA_DONE = {
  ...MEDIA_PENDING,
  id: 'raw-2',
  filename: '客户通话.m4a',
  structure_status: 'done',
  structure_kind: 'qa',
  qa_count: 28,
}

const TEXT_RAW = {
  ...MEDIA_PENDING,
  id: 'raw-3',
  filename: 'dialogues.csv',
  format: 'csv',
}

function renderPanel(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <RawDataPanel datasourceId="ds-1" {...props} />
    </QueryClientProvider>
  )
}

describe('RawDataPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRawData.mockResolvedValue({ items: [MEDIA_DONE, MEDIA_PENDING, TEXT_RAW] })
    structureRawData.mockResolvedValue({ task_id: 't-1', message: 'queued' })
  })

  it('只展示音视频文件，并给出转写/切分状态', async () => {
    renderPanel()

    expect(await screen.findByText('众联一面.mp3')).toBeInTheDocument()
    expect(screen.getByText('客户通话.m4a')).toBeInTheDocument()
    // 文本文件不进入该面板
    expect(screen.queryByText('dialogues.csv')).toBeNull()

    expect(screen.getByText('已切分')).toBeInTheDocument()
    expect(screen.getByText('28 组问答')).toBeInTheDocument()
    expect(screen.getByText('未切分')).toBeInTheDocument()
    // 两个音视频文件时长相同
    expect(screen.getAllByText('39 分 25 秒')).toHaveLength(2)
  })

  it('未切分文件提供「切分」，点击后调用接口', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText('众联一面.mp3')

    const buttons = screen.getAllByRole('button', { name: /切分/ })
    const pending = buttons.find(button => button.textContent.trim() === '切分')
    await user.click(pending)

    await waitFor(() => expect(structureRawData).toHaveBeenCalledWith('ds-1', 'raw-1'))
  })

  it('已切分文件显示「重新切分」', async () => {
    renderPanel()

    expect(await screen.findByRole('button', { name: '重新切分' })).toBeInTheDocument()
  })

  it('未完成转写时禁用切分按钮', async () => {
    listRawData.mockResolvedValue({
      items: [{ ...MEDIA_PENDING, asr_status: 'pending' }],
    })

    renderPanel()

    const button = await screen.findByRole('button', { name: '切分' })
    expect(button).toBeDisabled()
  })

  it('切分失败时展示原因', async () => {
    listRawData.mockResolvedValue({
      items: [
        {
          ...MEDIA_PENDING,
          structure_status: 'failed',
          error: 'structure=summary but summary is empty',
        },
      ],
    })

    renderPanel()

    expect(await screen.findByText('structure=summary but summary is empty')).toBeInTheDocument()
    expect(screen.getByText('切分失败')).toBeInTheDocument()
  })

  it('没有音视频文件时整个面板不渲染', async () => {
    listRawData.mockResolvedValue({ items: [TEXT_RAW] })

    renderPanel()

    await waitFor(() => expect(screen.queryByText('转写文件')).toBeNull())
  })

  it('无数据源时不请求', () => {
    renderPanel({ datasourceId: null })

    expect(listRawData).not.toHaveBeenCalled()
  })
})
