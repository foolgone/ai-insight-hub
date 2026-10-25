import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Select } from './Select'

const OPTIONS = [
  { label: '客服对话', value: 'customer_service' },
  { label: '销售话术', value: 'sales' },
]

describe('Select', () => {
  it('点击后展开选项列表', async () => {
    const user = userEvent.setup()
    render(<Select options={OPTIONS} value="" onChange={() => {}} />)

    await user.click(screen.getByRole('combobox'))

    expect(await screen.findByRole('listbox')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '客服对话' })).toBeInTheDocument()
  })

  it('单选后回传值并关闭', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Select options={OPTIONS} value="" onChange={onChange} />)

    await user.click(screen.getByRole('combobox'))
    await user.click(screen.getByRole('option', { name: '销售话术' }))

    expect(onChange).toHaveBeenCalledWith('sales')
    await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull())
  })

  it('多选以数组回传并可取消', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Select options={OPTIONS} value={['customer_service']} multiple onChange={onChange} />)

    await user.click(screen.getByRole('combobox'))
    await user.click(screen.getByRole('option', { name: '销售话术' }))

    expect(onChange).toHaveBeenCalledWith(['customer_service', 'sales'])
  })

  it('searchable 按关键字过滤选项', async () => {
    const user = userEvent.setup()
    render(<Select options={OPTIONS} value="" searchable onChange={() => {}} />)

    await user.click(screen.getByRole('combobox'))
    await user.type(screen.getByRole('textbox', { name: '搜索选项' }), '销售')

    expect(screen.getByRole('option', { name: '销售话术' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: '客服对话' })).toBeNull()
  })

  it('disabled 时不展开', async () => {
    const user = userEvent.setup()
    render(<Select options={OPTIONS} value="" disabled onChange={() => {}} />)

    const trigger = screen.getByRole('combobox')
    expect(trigger).toBeDisabled()
    await user.click(trigger)
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('error 渲染错误提示并标记 aria-invalid', () => {
    render(<Select options={OPTIONS} value="" error="请选择数据源" onChange={() => {}} />)

    expect(screen.getByRole('combobox')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('请选择数据源')
  })
})
