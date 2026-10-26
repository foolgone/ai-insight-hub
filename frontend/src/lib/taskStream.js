/**
 * 任务进度 SSE 客户端（T11）。
 *
 * 用 `fetch` + ReadableStream 而非 EventSource：EventSource 不能自定义
 * `Authorization` 头，而我们要走 Bearer access token。
 *
 * 协议：服务端推 `event: tasks\ndata: {"items":[...]}\n\n`，15s 心跳为 `: keep-alive`。
 * 断线自动重连（指数退避，上限 30s），返回的 `unsubscribe` 负责关闭。
 */
import { API_PREFIX, endpoints } from '../api/endpoints'
import { getAccessToken } from './token'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || API_PREFIX
const MAX_RETRY_DELAY = 30000

/**
 * 解析单个 SSE 帧（到空行为止）。
 * @param {string} raw
 * @returns {{ event: string, data: string } | null}
 */
export function parseEventChunk(raw) {
  const lines = raw.split('\n')
  const event =
    lines
      .find(line => line.startsWith('event:'))
      ?.slice(6)
      .trim() || 'message'
  const data = lines
    .filter(line => line.startsWith('data:'))
    .map(line => line.slice(5).trim())
    .join('\n')
  if (!data) return null
  return { event, data }
}

/**
 * 订阅任务流。
 * @param {{
 *   onTasks?: (payload: { items: Array }) => void,
 *   onOpen?: () => void,
 *   onError?: (error: unknown) => void,
 * }} handlers
 * @returns {() => void} 取消订阅
 */
export function subscribeTaskStream({ onTasks, onOpen, onError } = {}) {
  let closed = false
  let controller = null
  let retry = 0
  let timer = null

  function scheduleReconnect() {
    if (closed) return
    retry += 1
    const delay = Math.min(1000 * 2 ** Math.min(retry, 5), MAX_RETRY_DELAY)
    timer = setTimeout(connect, delay)
  }

  async function connect() {
    if (closed) return
    controller = new AbortController()
    try {
      const token = getAccessToken()
      const response = await fetch(`${BASE_URL}${endpoints.tasks.stream}`, {
        headers: {
          Accept: 'text/event-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        throw new Error(`SSE connect failed: ${response.status}`)
      }
      retry = 0
      onOpen?.()
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (!closed) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let index = buffer.indexOf('\n\n')
        while (index >= 0) {
          const raw = buffer.slice(0, index)
          buffer = buffer.slice(index + 2)
          const parsed = parseEventChunk(raw)
          if (parsed?.event === 'tasks') {
            try {
              onTasks?.(JSON.parse(parsed.data))
            } catch {
              // 忽略脏数据帧，不影响后续推送
            }
          }
          index = buffer.indexOf('\n\n')
        }
      }
    } catch (error) {
      if (closed || controller?.signal.aborted) return
      onError?.(error)
      scheduleReconnect()
      return
    }
    // 服务端正常关闭 → 重连
    scheduleReconnect()
  }

  connect()

  return () => {
    closed = true
    clearTimeout(timer)
    controller?.abort()
  }
}
