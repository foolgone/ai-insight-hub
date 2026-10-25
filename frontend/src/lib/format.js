import { format } from 'date-fns'

/**
 * 日期时间格式化；空值/非法值返回「—」。
 * @param {string|number|Date|null|undefined} value
 * @returns {string}
 */
export function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return format(date, 'yyyy-MM-dd HH:mm')
}

/**
 * 数字千分位格式化。
 * @param {number|string|null|undefined} value
 * @returns {string}
 */
export function formatNumber(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value) || 0)
}
