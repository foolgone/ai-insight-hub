import { Badge } from '../Badge'

/**
 * Judge Beta / 已知限制提示。
 * 产品口径：v1.2.5 为 frozen/inactive beta；invalid 与 known issues 只展示、不阻塞平台。
 * @param {{ issues?: Array<{key: string, label: string, count: number}>, className?: string }} props
 */
export function RagBetaNotice({ issues = [], className = '' }) {
  return (
    <div
      role="note"
      aria-label="评测 Beta 与已知限制"
      className={`rounded-md border border-warning-500/30 bg-warning-50/60 p-4 text-sm text-warning-800 ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="warning" size="sm">
          Beta
        </Badge>
        <p className="font-medium">Judge 评测为 beta，结果需结合人工复核</p>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-warning-700">
        v1.2.5 保持 frozen / inactive；invalid、skipped 与失败会原样展示，不隐藏、不阻塞平台。
        人工复核可以覆盖单条结论。
      </p>
      {issues.length ? (
        <ul className="mt-2 flex flex-wrap gap-2" aria-label="已知限制计数">
          {issues.map(issue => (
            <li key={issue.key}>
              <Badge variant="warning" size="sm">
                {issue.label} {issue.count}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
