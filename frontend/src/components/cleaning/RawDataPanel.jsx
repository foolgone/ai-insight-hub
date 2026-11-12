import { LuRefreshCw } from 'react-icons/lu'
import { Badge } from '../Badge'
import { Button } from '../Button'
import { useRawDataQuery, useStructureRawData } from '../../hooks/useDataSources'
import { formatDateTime } from '../../lib/format'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const ASR_STATUS = {
  completed: { label: '已转写', variant: 'success' },
  pending: { label: '转写中', variant: 'warning' },
  failed: { label: '转写失败', variant: 'error' },
}

const STRUCTURE_STATUS = {
  done: { label: '已切分', variant: 'success' },
  pending: { label: '未切分', variant: 'warning' },
  failed: { label: '切分失败', variant: 'error' },
  // 短音频 / 关闭结构化：不切分，但整段文本已保留
  skipped: { label: '无需切分', variant: 'info' },
}

function formatDuration(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value) || value <= 0) return '—'
  const minutes = Math.floor(value / 60)
  const rest = Math.round(value % 60)
  return minutes ? `${minutes} 分 ${rest} 秒` : `${rest} 秒`
}

/**
 * 转写文件面板（转写与切分拆开后的入口）。
 *
 * 只展示音视频文件：转写状态 + 切分状态 + 「重新切分」。
 * 重新切分会替换该文件的对话结果（后端整体替换，不会再产生重复）。
 *
 * @param {{ datasourceId?: string|null }} props
 */
export function RawDataPanel({ datasourceId = null }) {
  const query = useRawDataQuery(datasourceId)
  const mutation = useStructureRawData()

  if (!datasourceId) return null

  const mediaItems = (query.data?.items || []).filter(item => item.format === 'media')
  // 没有音视频时整个面板不出现（纯文本上传不需要切分）
  if (!query.isLoading && mediaItems.length === 0) return null

  const handleRestructure = async item => {
    try {
      await mutation.mutateAsync({ datasourceId, rawId: item.id })
      notify.success('切分任务已入队，完成后会自动刷新结果')
    } catch (error) {
      notify.error(getErrorMessage(error))
    }
  }

  return (
    <div className="rounded-md border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">转写文件</h2>
          <p className="mt-1 text-sm text-gray-600">
            转写与切分是两步：转写完成会自动切分；切分失败或效果不好时，可对单个文件重新切分（不会重复转写）。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          icon={<LuRefreshCw className="h-4 w-4" />}
          onClick={() => query.refetch()}
          loading={query.isFetching}
        >
          刷新
        </Button>
      </div>

      {query.isError ? (
        <p role="alert" className="mt-3 text-sm text-error-600">
          {getErrorMessage(query.error)}
        </p>
      ) : query.isLoading ? (
        <p className="mt-3 text-sm text-gray-500">正在加载文件...</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">音视频文件的转写与切分状态</caption>
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-600">
                <th scope="col" className="py-2 font-medium">
                  文件
                </th>
                <th scope="col" className="py-2 font-medium">
                  时长
                </th>
                <th scope="col" className="py-2 font-medium">
                  转写
                </th>
                <th scope="col" className="py-2 font-medium">
                  切分
                </th>
                <th scope="col" className="py-2 font-medium">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {mediaItems.map(item => {
                const asr = ASR_STATUS[item.asr_status] || ASR_STATUS.pending
                const structure =
                  STRUCTURE_STATUS[item.structure_status] || STRUCTURE_STATUS.pending
                const canStructure = item.asr_status === 'completed'
                return (
                  <tr key={item.id} className="border-b border-gray-100 align-top">
                    <td className="max-w-[220px] py-2">
                      <p className="truncate font-medium text-gray-800" title={item.filename}>
                        {item.filename || '未命名文件'}
                      </p>
                      <p className="text-xs text-gray-500">{formatDateTime(item.created_at)}</p>
                    </td>
                    <td className="py-2 text-gray-700">{formatDuration(item.duration)}</td>
                    <td className="py-2">
                      <Badge variant={asr.variant} size="sm">
                        {asr.label}
                      </Badge>
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={structure.variant} size="sm">
                          {structure.label}
                        </Badge>
                        {item.structure_status === 'done' ? (
                          <span className="text-xs text-gray-600">
                            {item.structure_kind === 'qa'
                              ? `${item.qa_count} 组问答`
                              : item.structure_kind === 'knowledge'
                                ? '知识点'
                                : '摘要'}
                            {item.partial ? '（部分）' : ''}
                          </span>
                        ) : null}
                      </div>
                      {item.error ? (
                        <p className="mt-1 max-w-[280px] text-xs text-error-600" title={item.error}>
                          {item.error}
                        </p>
                      ) : null}
                      {item.note ? (
                        <p className="mt-1 max-w-[280px] text-xs text-gray-500" title={item.note}>
                          {item.note}
                        </p>
                      ) : null}
                    </td>
                    <td className="py-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!canStructure}
                        loading={mutation.isPending && mutation.variables?.rawId === item.id}
                        onClick={() => handleRestructure(item)}
                      >
                        {item.structure_status === 'done' ? '重新切分' : '切分'}
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default RawDataPanel
