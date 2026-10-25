import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Checkbox } from './Checkbox'

describe('Checkbox', () => {
  it('渲染 label 并关联复选框', () => {
    render(<Checkbox label="同意协议" checked={false} onCheckedChange={() => {}} />)

    expect(screen.getByRole('checkbox', { name: '同意协议' })).toBeInTheDocument()
  })

  it('点击 label 触发 onCheckedChange(true)', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(<Checkbox label="去重" checked={false} onCheckedChange={onCheckedChange} />)

    await user.click(screen.getByText('去重'))

    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('选中态带 data-state=checked', () => {
    render(<Checkbox label="已选" checked onCheckedChange={() => {}} />)

    expect(screen.getByRole('checkbox', { name: '已选' })).toHaveAttribute('data-state', 'checked')
  })

  it('indeterminate 渲染部分选中态', () => {
    render(<Checkbox label="部分" checked={false} indeterminate onCheckedChange={() => {}} />)

    const checkbox = screen.getByRole('checkbox', { name: '部分' })
    expect(checkbox).toHaveAttribute('data-state', 'indeterminate')
  })

  it('disabled 时不可点击', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(<Checkbox label="禁用" checked={false} disabled onCheckedChange={onCheckedChange} />)

    await user.click(screen.getByRole('checkbox', { name: '禁用' }))

    expect(onCheckedChange).not.toHaveBeenCalled()
    expect(screen.getByRole('checkbox', { name: '禁用' })).toBeDisabled()
  })

  it('已选中时再次点击回传 false', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(<Checkbox label="已选" checked onCheckedChange={onCheckedChange} />)

    await user.click(screen.getByRole('checkbox', { name: '已选' }))

    expect(onCheckedChange).toHaveBeenCalledWith(false)
  })
})
