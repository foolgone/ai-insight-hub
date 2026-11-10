import { useQuery } from '@tanstack/react-query'
import * as insightsApi from '../api/insights'

export const insightKeys = {
  all: ['insights'],
  summaries: datasourceId => ['insights', 'summaries', datasourceId],
}

/** 转写摘要（无数据源时不请求）。 */
export function useSummariesQuery(datasourceId) {
  return useQuery({
    queryKey: insightKeys.summaries(datasourceId),
    queryFn: () => insightsApi.listTranscriptSummaries(datasourceId),
    enabled: Boolean(datasourceId),
    staleTime: 30_000,
  })
}
