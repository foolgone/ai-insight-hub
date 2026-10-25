import { Drawer } from '../Drawer'
import { Badge } from '../Badge'
import { formatDateTime } from '../../lib/format'

function Section({ title, children }) {
  return (
    <section className="space-y-1">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      <div className="text-sm text-gray-600">{children}</div>
    </section>
  )
}

/**
 * 清洗结果详情（F-208）：列表项不含 id，直接展示列表返回字段。
 * @param {{ item: Object|null, open: boolean, onClose: () => void }} props
 */
export function CleanedDataDrawer({ item, open, onClose }) {
  if (!item) return null

  const issues = Array.isArray(item.issues) ? item.issues : []
  const metadata = item.metadata && typeof item.metadata === 'object' ? item.metadata : {}

  return (
    <Drawer open={open} onClose={onClose} title="清洗结果详情">
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
          <span>对话 ID：{item.dialogue_id}</span>
          <span>时间：{formatDateTime(item.timestamp)}</span>
        </div>

        <Section title="用户消息">
          <p className="whitespace-pre-wrap rounded bg-gray-50 p-3">{item.user_message}</p>
        </Section>

        <Section title="AI 回复">
          <p className="whitespace-pre-wrap rounded bg-gray-50 p-3">{item.ai_response}</p>
        </Section>

        <Section title="质量与问题">
          <div className="flex items-center gap-2">
            <span>质量分：{Number(item.quality_score ?? 0).toFixed(1)}</span>
            {issues.length > 0 ? (
              <Badge variant="warning" size="sm">
                {issues.length} 个问题
              </Badge>
            ) : (
              <Badge variant="success" size="sm">
                无问题
              </Badge>
            )}
          </div>
          {issues.length > 0 ? (
            <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-gray-600">
              {issues.map(issue => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          ) : null}
        </Section>

        {Object.keys(metadata).length > 0 ? (
          <Section title="元数据">
            <dl className="space-y-1 text-xs">
              {Object.entries(metadata).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="text-gray-500">{key}</dt>
                  <dd className="text-right text-gray-700">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </Section>
        ) : null}
      </div>
    </Drawer>
  )
}
