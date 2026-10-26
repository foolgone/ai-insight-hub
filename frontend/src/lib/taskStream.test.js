import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { parseEventChunk, subscribeTaskStream } from './taskStream'
import { clearAccessToken, setAccessToken } from './token'

function sseStream() {
  const encoder = new TextEncoder()
  let controller
  const stream = new ReadableStream({
    start(inner) {
      controller = inner
    },
  })
  return {
    stream,
    push: text => controller.enqueue(encoder.encode(text)),
    close: () => controller.close(),
  }
}

describe('lib/taskStream', () => {
  beforeEach(() => {
    setAccessToken('token-1')
  })

  afterEach(() => {
    clearAccessToken()
    vi.unstubAllGlobals()
  })

  it('parseEventChunk 解析 event/data', () => {
    expect(parseEventChunk('event: tasks\ndata: {"items":[]}')).toEqual({
      event: 'tasks',
      data: '{"items":[]}',
    })
    expect(parseEventChunk(': keep-alive')).toBeNull()
  })

  it('订阅后按帧回调 onTasks，并携带 Bearer 令牌', async () => {
    const { stream, push, close } = sseStream()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: stream })
    vi.stubGlobal('fetch', fetchMock)
    const onTasks = vi.fn()
    const onOpen = vi.fn()

    const unsubscribe = subscribeTaskStream({ onTasks, onOpen })

    push('event: tasks\ndata: {"items":[{"id":"t-1","status":"running"}]}\n\n')
    await vi.waitFor(() => expect(onTasks).toHaveBeenCalledTimes(1))
    close()
    unsubscribe()

    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onTasks.mock.calls[0][0].items[0]).toMatchObject({ id: 't-1', status: 'running' })
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tasks/stream'),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-1' }),
        credentials: 'include',
      })
    )
  })

  it('连接失败时回调 onError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    const onError = vi.fn()

    const unsubscribe = subscribeTaskStream({ onError })
    await vi.waitFor(() => expect(onError).toHaveBeenCalled())
    unsubscribe()
  })
})
