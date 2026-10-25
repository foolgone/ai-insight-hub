import { Badge } from '../Badge'
import { Button } from '../Button'
import { Popconfirm } from '../Popconfirm'
import { formatDateTime } from '../../lib/format'

const SOURCE_LABELS = {
  seed: '种子',
  manual: '手动',
  extracted: '提取',
}

/**
 * 知识条目卡片（02 §6.4 / 03 §3.6）。
 * @param {{
 *   entry: Object,
 *   canWrite?: boolean,
 *   onEdit?: () => void,
 *   onDelete?: () => void,
 *   searchSimilarity?: number,
 * }} props
 */
export function KnowledgeEntryCard({ entry, canWrite = true, onEdit, onDelete, searchSimilarity }) {
  const tags = Array.isArray(entry.tags) ? entry.tags : []
  const visibleTags = tags.slice(0, 3)

  return (
    <article className="rounded-md border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-gray-900">{entry.question}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-gray-500">
            {entry.category ? (
              <Badge variant="info" size="sm">
                {entry.category}
              </Badge>
            ) : null}
            {visibleTags.map(tag => (
              <Badge key={tag} variant="default" size="sm">
                {tag}
              </Badge>
            ))}
            {tags.length > visibleTags.length ? (
              <span>+{tags.length - visibleTags.length}</span>
            ) : null}
            {searchSimilarity !== undefined && searchSimilarity !== null ? (
              <span>相似度 {Math.round(Number(searchSimilarity) * 100)}%</span>
            ) : null}
          </div>
        </div>

        {canWrite ? (
          <div className="flex shrink-0 items-center gap-1">
            {onEdit ? (
              <Button size="sm" variant="ghost" onClick={onEdit}>
                编辑
              </Button>
            ) : null}
            {onDelete ? (
              <Popconfirm
                title="删除该知识条目？"
                description="删除后不可恢复。"
                onConfirm={onDelete}
              >
                <Button size="sm" variant="ghost">
                  删除
                </Button>
              </Popconfirm>
            ) : null}
          </div>
        ) : null}
      </div>

      <p className="mt-2 line-clamp-2 text-sm text-gray-600">{entry.answer}</p>

      <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        <div className="flex gap-1">
          <dt>来源：</dt>
          <dd className="text-gray-700">{SOURCE_LABELS[entry.source] || entry.source || '—'}</dd>
        </div>
        {entry.confidence !== undefined && entry.confidence !== null ? (
          <div className="flex gap-1">
            <dt>置信度：</dt>
            <dd className="text-gray-700">{Math.round(Number(entry.confidence) * 100)}%</dd>
          </div>
        ) : null}
        {entry.quality_score !== undefined && entry.quality_score !== null ? (
          <div className="flex gap-1">
            <dt>质量分：</dt>
            <dd className="text-gray-700">{Number(entry.quality_score).toFixed(1)}</dd>
          </div>
        ) : null}
        {entry.frequency !== undefined && entry.frequency !== null ? (
          <div className="flex gap-1">
            <dt>频次：</dt>
            <dd className="text-gray-700">{entry.frequency}</dd>
          </div>
        ) : null}
        {entry.created_at ? (
          <div className="flex gap-1">
            <dt>创建：</dt>
            <dd className="text-gray-700">{formatDateTime(entry.created_at)}</dd>
          </div>
        ) : null}
      </dl>
    </article>
  )
}
