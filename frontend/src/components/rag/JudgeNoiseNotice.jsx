import { Badge } from '../Badge'

/**
 * Judge β 噪声提示：固定展示；同配置比较时升级为强警告。
 * 产品口径：delta 不是因果结论，同配置/同输入也可能 ±0.2 波动。
 * @param {{ sameConfig?: boolean, className?: string }} props
 */
export function JudgeNoiseNotice({ sameConfig = false, className = '' }) {
  return (
    <div
      role="note"
      aria-label="Judge β 噪声提示"
      className={`rounded-md border border-info-500/30 bg-info-50/60 p-4 text-sm text-info-900 ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="info" size="sm">
          β 噪声
        </Badge>
        <p className="font-medium">Judge 为 beta：同配置 / 同输入的两条 Run 也可能出现 ±0.2 波动</p>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-info-800">
        delta 不代表因果变化。建议重复 3 次，或先确认 RAG 输入与配置确实不同，再判断“有没有变好”。
      </p>
      {sameConfig ? (
        <p
          role="alert"
          className="mt-2 rounded border border-warning-500/30 bg-warning-50 p-2 text-xs text-warning-800"
        >
          同配置比较：两条 Run 的数据集/版本、adapter、mode、top_k 相同（或配置字段不可得）。 当前
          delta 主要反映 Judge 评分噪声，不能作为优化结论。
        </p>
      ) : null}
    </div>
  )
}
