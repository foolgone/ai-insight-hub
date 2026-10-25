import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QualityScoreDisplay } from './QualityScoreDisplay'

describe('QualityScoreDisplay', () => {
  it.each([
    [95, '优秀'],
    [80, '良好'],
    [65, '合格'],
    [50, '较差'],
  ])('score=%s 显示等级 %s', (score, label) => {
    render(<QualityScoreDisplay score={score} />)

    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: `质量分 ${score}` })).toBeInTheDocument()
  })

  it('显示四舍五入后的分数', () => {
    render(<QualityScoreDisplay score={82.6} />)

    expect(screen.getByText('83')).toBeInTheDocument()
  })

  it('可隐藏等级标签', () => {
    render(<QualityScoreDisplay score={80} showLevel={false} />)

    expect(screen.queryByText('良好')).toBeNull()
  })

  it('支持尺寸', () => {
    render(<QualityScoreDisplay score={80} size="lg" />)

    expect(screen.getByRole('img', { name: '质量分 80' })).toHaveClass('h-full')
  })
})
