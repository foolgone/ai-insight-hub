import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as ragApi from '../api/ragEvaluations'

export const ragEvaluationKeys = {
  all: ['rag-evaluations'],
  list: (params = {}) => ['rag-evaluations', 'list', params],
  detail: runId => ['rag-evaluations', 'detail', runId],
  results: (runId, params = {}) => ['rag-evaluations', 'results', runId, params],
  failures: (runId, params = {}) => ['rag-evaluations', 'failures', runId, params],
  trace: traceId => ['rag-traces', traceId],
  datasets: (params = {}) => ['qa-datasets', 'list', params],
  versions: datasetId => ['qa-datasets', 'versions', datasetId],
  items: (datasetId, versionId, params = {}) => [
    'qa-datasets',
    'items',
    datasetId,
    versionId,
    params,
  ],
  item: (datasetId, versionId, itemId) => ['qa-datasets', 'item', datasetId, versionId, itemId],
}

const ACTIVE_STATUSES = new Set(['pending', 'queued', 'running'])

/** 评测 Run 列表；有 running/queued 时 5s 轮询。 */
export function useRagEvaluationsQuery(params = {}, options = {}) {
  return useQuery({
    queryKey: ragEvaluationKeys.list(params),
    queryFn: () => ragApi.listRagEvaluations(params),
    refetchInterval: query => {
      const items = query.state.data?.items || []
      return items.some(item => ACTIVE_STATUSES.has(item.status)) ? 5000 : false
    },
    ...options,
  })
}

/** Run 详情；运行中轮询。 */
export function useRagEvaluationQuery(runId, options = {}) {
  return useQuery({
    queryKey: ragEvaluationKeys.detail(runId),
    queryFn: () => ragApi.getRagEvaluation(runId),
    enabled: Boolean(runId),
    refetchInterval: query => (ACTIVE_STATUSES.has(query.state.data?.status) ? 5000 : false),
    ...options,
  })
}

export function useRagEvaluationResultsQuery(runId, params = {}, options = {}) {
  return useQuery({
    queryKey: ragEvaluationKeys.results(runId, params),
    queryFn: () => ragApi.listRagEvaluationResults(runId, params),
    enabled: Boolean(runId),
    ...options,
  })
}

export function useAllRagEvaluationResultsQuery(runId, { maxRows = 1000 } = {}, options = {}) {
  return useQuery({
    queryKey: ['rag-evaluations', 'all-results', runId, maxRows],
    queryFn: () => ragApi.listAllRagEvaluationResults(runId, { maxRows }),
    enabled: Boolean(runId),
    ...options,
  })
}

export function useRagEvaluationFailuresQuery(runId, params = {}, options = {}) {
  return useQuery({
    queryKey: ragEvaluationKeys.failures(runId, params),
    queryFn: () => ragApi.listRagEvaluationFailures(runId, params),
    enabled: Boolean(runId),
    ...options,
  })
}

export function useRagTraceQuery(traceId) {
  return useQuery({
    queryKey: ragEvaluationKeys.trace(traceId),
    queryFn: () => ragApi.getRagTrace(traceId),
    enabled: Boolean(traceId),
  })
}

export function useDatasetsQuery(enabled = true) {
  return useQuery({
    queryKey: ragEvaluationKeys.datasets({ limit: 100 }),
    queryFn: () => ragApi.listDatasets({ limit: 100 }),
    enabled,
  })
}

export function useDatasetVersionsQuery(datasetId) {
  return useQuery({
    queryKey: ragEvaluationKeys.versions(datasetId),
    queryFn: () => ragApi.listDatasetVersions(datasetId),
    enabled: Boolean(datasetId),
  })
}

export function useDatasetItemsQuery(datasetId, versionId, options = {}) {
  return useQuery({
    queryKey: ragEvaluationKeys.items(datasetId, versionId, { limit: 100 }),
    queryFn: () => ragApi.listDatasetItems(datasetId, versionId, { limit: 100 }),
    enabled: Boolean(datasetId && versionId),
    ...options,
  })
}

export function useDatasetItemQuery(datasetId, versionId, itemId) {
  return useQuery({
    queryKey: ragEvaluationKeys.item(datasetId, versionId, itemId),
    queryFn: () => ragApi.getDatasetItem(datasetId, versionId, itemId),
    enabled: Boolean(datasetId && versionId && itemId),
  })
}

/** 新建评测：成功后失效列表。 */
export function useCreateRagEvaluation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: payload => ragApi.createRagEvaluation(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ragEvaluationKeys.all }),
  })
}
