import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RadioGroup } from './Radio'

const OPTIONS = [
  { label: '优秀', value: 'excellent' },
  { label: '良好', value: 'good' },
]

describe('RadioGroup', () => {
  it('渲染全部选项', () => {
    render(<RadioGroup options={OPTIONS} value="" onChange={() => {}} />)

    expect(screen.getByRole('radio', { name: '优秀' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '良好' })).toBeInTheDocument()
  })

  it('点击选项触发 onChange', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<RadioGroup options={OPTIONS} value="" onChange={onChange} />)

    await user.click(screen.getByText('良好'))

    expect(onChange).toHaveBeenCalledWith('good')
  })

  it('选中项 aria-checked 为 true', () => {
    render(<RadioGroup options={OPTIONS} value="excellent" onChange={() => {}} />)

    expect(screen.getByRole('radio', { name: '优秀' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: '良好' })).toHaveAttribute('aria-checked', 'false')
  })

  it('组级 disabled 禁用所有选项', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<RadioGroup options={OPTIONS} value="" disabled onChange={onChange} />)

    await user.click(screen.getByText('优秀'))

    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: '优秀' })).toBeDisabled()
  })

  it('单个选项可禁用', () => {
    render(
      <RadioGroup
        options={[OPTIONS[0], { ...OPTIONS[1], disabled: true }]}
        value=""
        onChange={() => {}}
      />
    )

    expect(screen.getByRole('radio', { name: '良好' })).toBeDisabled()
  })
})
