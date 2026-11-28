import { useQuery } from '@tanstack/react-query'
import * as qaDatasetApi from '../api/qaDatasets'

export const qaDatasetKeys = {
  all: ['qa-datasets'],
  list: (params = {}) => ['qa-datasets', 'list', params],
  detail: datasetId => ['qa-datasets', 'detail', datasetId],
  stats: (datasetId, versionId) => ['qa-datasets', 'stats', datasetId, versionId],
  items: (datasetId, versionId, params = {}) => [
    'qa-datasets',
    'items',
    datasetId,
    versionId,
    params,
  ],
}

export function useQaDatasetsQuery(params = {}, options = {}) {
  return useQuery({
    queryKey: qaDatasetKeys.list(params),
    queryFn: () => qaDatasetApi.listQaDatasets(params),
    ...options,
  })
}

export function useQaDatasetQuery(datasetId, options = {}) {
  return useQuery({
    queryKey: qaDatasetKeys.detail(datasetId),
    queryFn: () => qaDatasetApi.getQaDataset(datasetId),
    enabled: Boolean(datasetId),
    ...options,
  })
}

export function useQaDatasetStatsQuery(datasetId, versionId, options = {}) {
  return useQuery({
    queryKey: qaDatasetKeys.stats(datasetId, versionId),
    queryFn: () => qaDatasetApi.getQaDatasetStats(datasetId, versionId),
    enabled: Boolean(datasetId && versionId),
    ...options,
  })
}

export function useQaDatasetItemsQuery(datasetId, versionId, params = {}, options = {}) {
  return useQuery({
    queryKey: qaDatasetKeys.items(datasetId, versionId, params),
    queryFn: () => qaDatasetApi.listQaDatasetItems(datasetId, versionId, params),
    enabled: Boolean(datasetId && versionId),
    ...options,
  })
}
