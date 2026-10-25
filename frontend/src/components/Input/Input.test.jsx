import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Input } from './Input'

describe('Input', () => {
  it('渲染占位符与受控值', () => {
    render(<Input value="hello" onChange={() => {}} placeholder="请输入" />)

    const input = screen.getByPlaceholderText('请输入')
    expect(input).toHaveValue('hello')
  })

  it('onChange 只回传字符串值', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Input value="" onChange={onChange} placeholder="名称" />)

    await user.type(screen.getByPlaceholderText('名称'), 'abc')

    expect(onChange).toHaveBeenCalledWith('a')
    expect(onChange).toHaveBeenLastCalledWith('c')
  })

  it('error 时设置 aria-invalid 与错误提示', () => {
    render(<Input value="" onChange={() => {}} error="名称不能为空" />)

    const input = screen.getByRole('textbox')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('名称不能为空')
    expect(screen.getByRole('alert')).toHaveTextContent('名称不能为空')
  })

  it('helperText 仅作辅助说明，不标记错误', () => {
    render(<Input value="" onChange={() => {}} helperText="最多 50 字" />)

    const input = screen.getByRole('textbox')
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(input).toHaveAccessibleDescription('最多 50 字')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('disabled 时不可输入', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Input value="" onChange={onChange} disabled />)

    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
    await user.type(input, 'x')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('渲染 prefix/suffix', () => {
    render(
      <Input
        value=""
        onChange={() => {}}
        prefix={<span data-testid="prefix-icon" />}
        suffix={<span data-testid="suffix-icon" />}
      />
    )

    expect(screen.getByTestId('prefix-icon')).toBeInTheDocument()
    expect(screen.getByTestId('suffix-icon')).toBeInTheDocument()
  })
})
