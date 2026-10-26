import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { subscribeTaskStream } from '../lib/taskStream'
import { taskKeys } from './useTasks'

/**
 * 订阅任务进度 SSE（T11）。
 *
 * - 收到 `tasks` 事件 → 失效任务相关 Query（由 React Query 重新拉取，避免手写缓存合并）；
 * - 连接成功返回 `connected=true`，页面据此关闭轮询兜底；失败自动重连并置 false。
 *
 * 测试环境（MODE=test）不建立连接，避免 jsdom 里的真实网络与重连定时器。
 * @param {boolean} [enabled]
 * @returns {{ connected: boolean }}
 */
export function useTaskStream(enabled = true) {
  const queryClient = useQueryClient()
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (!enabled || import.meta.env.MODE === 'test') {
      setConnected(false)
      return undefined
    }
    const unsubscribe = subscribeTaskStream({
      onOpen: () => setConnected(true),
      onError: () => setConnected(false),
      onTasks: () => {
        queryClient.invalidateQueries({ queryKey: taskKeys.all })
      },
    })
    return () => {
      setConnected(false)
      unsubscribe()
    }
  }, [enabled, queryClient])

  return { connected }
}
