import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as knowledgeApi from '../api/knowledge'
import { taskKeys } from './useTasks'

export const knowledgeKeys = {
  all: ['knowledge'],
  faq: (datasourceId, params) => ['knowledge', 'faq', datasourceId, params],
  gaps: datasourceId => ['knowledge', 'gaps', datasourceId],
  search: (datasourceId, params) => ['knowledge', 'search', datasourceId, params],
}

/**
 * FAQ 无限列表（分页递增，供「加载更多」）。
 * @param {string|null|undefined} datasourceId
 * @param {Object} [params]
 * @param {Object} [options]
 */
export function useFaqInfiniteQuery(datasourceId, params = {}, options = {}) {
  return useInfiniteQuery({
    queryKey: knowledgeKeys.faq(datasourceId, params),
    queryFn: ({ pageParam = 1 }) =>
      knowledgeApi.listFaq(datasourceId, { ...params, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: lastPage => {
      const pagination = lastPage?.pagination
      return pagination?.has_next ? pagination.page + 1 : undefined
    },
    enabled: Boolean(datasourceId),
    ...options,
  })
}

/**
 * 知识检索（关键词非空才请求）。
 * @param {string|null|undefined} datasourceId
 * @param {string} term
 * @param {{ limit?: number }} [params]
 */
export function useKnowledgeSearchQuery(datasourceId, term, params = {}) {
  return useQuery({
    queryKey: knowledgeKeys.search(datasourceId, { term, ...params }),
    queryFn: () => knowledgeApi.searchKnowledge(datasourceId, { q: term, ...params }),
    enabled: Boolean(datasourceId && term),
  })
}

/**
 * 知识盲区。
 * @param {string|null|undefined} datasourceId
 */
export function useGapsQuery(datasourceId) {
  return useQuery({
    queryKey: knowledgeKeys.gaps(datasourceId),
    queryFn: () => knowledgeApi.listGaps(datasourceId),
    enabled: Boolean(datasourceId),
  })
}

/** 触发知识提取（202）。 */
export function useExtractKnowledge() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, payload }) => knowledgeApi.extractKnowledge(datasourceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.all })
      queryClient.invalidateQueries({ queryKey: knowledgeKeys.all })
    },
  })
}

/** 创建 FAQ。 */
export function useCreateFaq() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, payload }) => knowledgeApi.createFaq(datasourceId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: knowledgeKeys.all }),
  })
}

/** 更新 FAQ。 */
export function useUpdateFaq() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, faqId, payload }) =>
      knowledgeApi.updateFaq(datasourceId, faqId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: knowledgeKeys.all }),
  })
}

/** 删除 FAQ。 */
export function useDeleteFaq() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ datasourceId, faqId }) => knowledgeApi.deleteFaq(datasourceId, faqId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: knowledgeKeys.all }),
  })
}
