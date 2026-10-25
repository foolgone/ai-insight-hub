import { Badge } from '../Badge'

const STATUS_MAP = {
  pending: { label: '排队中', variant: 'default' },
  running: { label: '进行中', variant: 'info' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失败', variant: 'error' },
  cancelled: { label: '已取消', variant: 'default' },
}

/**
 * Agent/任务状态徽章（02 §6.2）：5 态映射。
 * @param {{ status: string, className?: string }} props
 */
export function AgentStatusBadge({ status, className }) {
  const meta = STATUS_MAP[status] || { label: status, variant: 'default' }
  return (
    <Badge variant={meta.variant} size="sm" className={className}>
      {meta.label}
    </Badge>
  )
}
