/** 5 个评估维度（与后端 Literal 一致，顺序用于展示）。 */
export const EVALUATION_DIMENSIONS = [
  { key: 'accuracy', label: '准确性' },
  { key: 'completeness', label: '完整性' },
  { key: 'hallucination', label: '幻觉控制' },
  { key: 'tone', label: '语气' },
  { key: 'compliance', label: '合规性' },
]

/**
 * @param {string} key
 * @returns {string}
 */
export function dimensionLabel(key) {
  return EVALUATION_DIMENSIONS.find(item => item.key === key)?.label || key
}
