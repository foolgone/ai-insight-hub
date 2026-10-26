import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Table } from './Table'

const COLUMNS = [
  { key: 'name', title: '名称', dataIndex: 'name' },
  { key: 'status', title: '状态', dataIndex: 'status' },
]
const DATA = [
  { id: '1', name: '客服对话', status: 'active' },
  { id: '2', name: '销售话术', status: 'processing' },
]

function bodyRows() {
  return screen.getAllByRole('row').slice(1)
}

describe('Table', () => {
  it('渲染表头与数据行', () => {
    render(<Table columns={COLUMNS} dataSource={DATA} rowKey="id" />)

    expect(screen.getByRole('columnheader', { name: '名称' })).toBeInTheDocument()
    expect(screen.getByText('客服对话')).toBeInTheDocument()
    expect(screen.getByText('销售话术')).toBeInTheDocument()
  })

  it('支持自定义 render', () => {
    render(
      <Table
        columns={[{ key: 'name', title: '名称', dataIndex: 'name', render: value => `#${value}` }]}
        dataSource={DATA}
        rowKey="id"
      />
    )

    expect(screen.getByText('#客服对话')).toBeInTheDocument()
  })

  it('空数据显示空态', () => {
    render(<Table columns={COLUMNS} dataSource={[]} emptyText="没有数据" />)

    expect(screen.getByText('没有数据')).toBeInTheDocument()
  })

  it('loading 时标记 aria-busy 并渲染骨架行', () => {
    render(<Table columns={COLUMNS} dataSource={DATA} loading />)

    expect(screen.getByRole('table')).toHaveAttribute('aria-busy', 'true')
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(5)
  })

  it('点击列头排序', async () => {
    const user = userEvent.setup()
    render(
      <Table
        columns={[{ key: 'name', title: '名称', dataIndex: 'name', sortable: true }]}
        dataSource={[
          { id: '1', name: 'b' },
          { id: '2', name: 'a' },
        ]}
      />
    )

    const header = screen.getByRole('columnheader', { name: /名称/ })
    expect(header).toHaveAttribute('aria-sort', 'none')

    await user.click(screen.getByRole('button', { name: /名称/ }))

    expect(header).toHaveAttribute('aria-sort', 'ascending')
    expect(bodyRows()[0]).toHaveTextContent('a')

    await user.click(screen.getByRole('button', { name: /名称/ }))
    expect(header).toHaveAttribute('aria-sort', 'descending')

    await user.click(screen.getByRole('button', { name: /名称/ }))
    expect(header).toHaveAttribute('aria-sort', 'none')
  })

  it('行选择回调返回选中键', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Table columns={COLUMNS} dataSource={DATA} rowSelection={{ selectedRowKeys: [], onChange }} />
    )

    await user.click(screen.getByRole('checkbox', { name: '选择 1' }))

    expect(onChange).toHaveBeenCalledWith(['1'])
  })

  it('全选当前页', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Table columns={COLUMNS} dataSource={DATA} rowSelection={{ selectedRowKeys: [], onChange }} />
    )

    await user.click(screen.getByRole('checkbox', { name: '全选当前页' }))

    expect(onChange).toHaveBeenCalledWith(['1', '2'])
  })

  it('分页按钮回调页码', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Table
        columns={COLUMNS}
        dataSource={DATA}
        pagination={{ current: 1, pageSize: 10, total: 25, onChange }}
      />
    )

    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '下一页' }))

    expect(onChange).toHaveBeenCalledWith(2, 10)
  })
})
