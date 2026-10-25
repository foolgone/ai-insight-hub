import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DataSourceActions } from './DataSourceActions'

const DATASOURCE = { id: 'ds-1', name: '客服1月' }

function setup(canWrite = true) {
  const handlers = {
    onDetail: vi.fn(),
    onEdit: vi.fn(),
    onUpload: vi.fn(),
    onDelete: vi.fn(),
  }
  render(<DataSourceActions datasource={DATASOURCE} canWrite={canWrite} {...handlers} />)
  return handlers
}

describe('DataSourceActions', () => {
  it('打开菜单展示全部操作（可写角色）', async () => {
    const user = userEvent.setup()
    setup(true)

    await user.click(screen.getByRole('button', { name: '数据源操作：客服1月' }))

    expect(await screen.findByRole('menuitem', { name: /查看详情/ })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /编辑信息/ })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /上传数据/ })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /删除数据源/ })).toBeInTheDocument()
  })

  it('viewer 只保留查看详情', async () => {
    const user = userEvent.setup()
    setup(false)

    await user.click(screen.getByRole('button', { name: '数据源操作：客服1月' }))

    expect(await screen.findByRole('menuitem', { name: /查看详情/ })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /编辑信息/ })).toBeNull()
    expect(screen.queryByRole('menuitem', { name: /删除数据源/ })).toBeNull()
  })

  it('点击操作触发对应回调', async () => {
    const user = userEvent.setup()
    const handlers = setup(true)

    await user.click(screen.getByRole('button', { name: '数据源操作：客服1月' }))
    await user.click(await screen.findByRole('menuitem', { name: /编辑信息/ }))
    expect(handlers.onEdit).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: '数据源操作：客服1月' }))
    await user.click(await screen.findByRole('menuitem', { name: /删除数据源/ }))
    expect(handlers.onDelete).toHaveBeenCalledTimes(1)
  })
})
