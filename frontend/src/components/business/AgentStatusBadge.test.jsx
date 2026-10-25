import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentStatusBadge } from './AgentStatusBadge'

describe('AgentStatusBadge', () => {
  it.each([
    ['pending', '排队中'],
    ['running', '进行中'],
    ['completed', '已完成'],
    ['failed', '失败'],
    ['cancelled', '已取消'],
  ])('status=%s 显示 %s', (status, label) => {
    render(<AgentStatusBadge status={status} />)

    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('未知状态回退显示原值', () => {
    render(<AgentStatusBadge status="unknown" />)

    expect(screen.getByText('unknown')).toBeInTheDocument()
  })
})
