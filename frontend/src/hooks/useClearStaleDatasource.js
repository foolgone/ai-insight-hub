import { useEffect } from 'react'
import { useDatasourceStore } from '../stores/datasourceStore'

/**
 * 当前选中的数据源已被删除/空库重置时，清理本地持久化的 currentId。
 * 只处理 404；网络错误和 5xx 保留选中项，避免短暂故障把用户上下文清掉。
 * @param {{ status?: number } | null | undefined} error
 * @param {string|null|undefined} datasourceId
 */
export function useClearStaleDatasource(error, datasourceId) {
  const clearCurrentId = useDatasourceStore(state => state.clearCurrentId)

  useEffect(() => {
    if (!datasourceId) return
    if (error?.status === 404) clearCurrentId()
  }, [error, datasourceId, clearCurrentId])
}
