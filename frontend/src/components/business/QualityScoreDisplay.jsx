import clsx from 'clsx'
import { Badge } from '../Badge'
import { qualityLevelForScore } from '../../lib/quality'

const SIZES = {
  sm: { box: 'h-16 w-16', text: 'text-lg', radius: 28 },
  md: { box: 'h-24 w-24', text: 'text-3xl', radius: 42 },
  lg: { box: 'h-32 w-32', text: 'text-4xl', radius: 56 },
}

/**
 * 质量分数展示（02 §6.3）：环形进度 + 分数 + 等级标签；等级按分数计算。
 * @param {{ score?: number, size?: 'sm'|'md'|'lg', showLevel?: boolean, className?: string }} props
 */
export function QualityScoreDisplay({ score = 0, size = 'md', showLevel = true, className }) {
  const safeScore = Math.min(100, Math.max(0, Number(score) || 0))
  const level = qualityLevelForScore(safeScore)
  const dimension = SIZES[size] || SIZES.md
  const radius = dimension.radius
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (safeScore / 100) * circumference

  return (
    <div className={clsx('inline-flex items-center gap-3', className)}>
      <div className={clsx('relative shrink-0', dimension.box)}>
        <svg
          viewBox="0 0 100 100"
          role="img"
          aria-label={`质量分 ${safeScore}`}
          className="h-full w-full -rotate-90"
        >
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            strokeWidth="8"
            className="stroke-gray-200"
          />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={clsx('transition-all', level.color)}
            style={{ stroke: 'currentColor' }}
          />
        </svg>
        <span
          className={clsx(
            'absolute inset-0 grid place-items-center font-bold text-gray-900',
            dimension.text
          )}
        >
          {Math.round(safeScore)}
        </span>
      </div>
      {showLevel ? (
        <Badge variant={level.variant} size="sm">
          {level.label}
        </Badge>
      ) : null}
    </div>
  )
}
