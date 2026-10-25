import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as taskApi from '../api/tasks'

/** 任务 Query key。 */
export const taskKeys = {
  all: ['tasks'],
  list: params => ['tasks', 'list', params],
  detail: id => ['tasks', 'detail', id],
}

/**
 * 任务列表查询（清洗页按 task_type=clean + 状态过滤）。
 * @param {Object} [params]
 * @param {Object} [options]
 */
export function useTasksQuery(params = {}, options = {}) {
  return useQuery({
    queryKey: taskKeys.list(params),
    queryFn: () => taskApi.listTasks(params),
    ...options,
  })
}

/**
 * 任务详情/进度查询。
 * @param {string|null|undefined} id
 * @param {Object} [options]
 */
export function useTaskQuery(id, options = {}) {
  return useQuery({
    queryKey: taskKeys.detail(id),
    queryFn: () => taskApi.getTask(id),
    enabled: Boolean(id),
    ...options,
  })
}

/** 取消任务并失效任务列表。 */
export function useCancelTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: taskApi.cancelTask,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: taskKeys.all }),
  })
}

/** 重试失败任务并失效任务列表。 */
export function useRetryTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: taskApi.retryTask,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: taskKeys.all }),
  })
}
