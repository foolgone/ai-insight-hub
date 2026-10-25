/** 质量等级（与后端 fair 枚举对齐，D-F18）。 */
export const QUALITY_LEVELS = [
  { key: 'excellent', label: '优秀', min: 90, variant: 'success', color: 'text-success-500' },
  { key: 'good', label: '良好', min: 75, variant: 'primary', color: 'text-primary-500' },
  { key: 'fair', label: '合格', min: 60, variant: 'warning', color: 'text-warning-500' },
  { key: 'poor', label: '较差', min: 0, variant: 'error', color: 'text-error-500' },
]

/**
 * 按总分计算质量等级（不依赖后端可能过期的 quality_level）。
 * @param {number} score 0–100
 * @returns {{ key: string, label: string, min: number, variant: string, color: string }}
 */
export function qualityLevelForScore(score) {
  const safe = Math.min(100, Math.max(0, Number(score) || 0))
  return (
    QUALITY_LEVELS.find(level => safe >= level.min) || QUALITY_LEVELS[QUALITY_LEVELS.length - 1]
  )
}

/**
 * 按分数统计 4 档分布。
 * @param {Array<{ overall_score?: number }>} items
 * @returns {Array<{ name: string, value: number, key: string }>}
 */
export function countQualityLevels(items = []) {
  const counts = Object.fromEntries(QUALITY_LEVELS.map(level => [level.key, 0]))
  items.forEach(item => {
    counts[qualityLevelForScore(item.overall_score).key] += 1
  })
  return QUALITY_LEVELS.map(level => ({
    key: level.key,
    name: level.label,
    value: counts[level.key],
  }))
}
