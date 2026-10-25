/** 数据源状态 → 文案/Badge 变体/圆点色。 */
export const DATASOURCE_STATUS = {
  active: { label: '已就绪', variant: 'success', dot: 'bg-success-500' },
  processing: { label: '处理中', variant: 'warning', dot: 'bg-warning-500' },
  archived: { label: '已归档', variant: 'default', dot: 'bg-gray-400' },
  error: { label: '异常', variant: 'error', dot: 'bg-error-500' },
}

/** 数据源类型 → 中文名。 */
export const DATASOURCE_TYPES = {
  customer_service: '客服对话',
  sales: '销售',
  support: '支持',
  other: '其他',
}

/**
 * @param {string} status
 * @returns {{ label: string, variant: 'default'|'success'|'warning'|'error', dot: string }}
 */
export function getDatasourceStatus(status) {
  return DATASOURCE_STATUS[status] || { label: status, variant: 'default', dot: 'bg-gray-400' }
}

/**
 * @param {string} type
 * @returns {string}
 */
export function getDatasourceTypeLabel(type) {
  return DATASOURCE_TYPES[type] || type
}
