import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Alert } from './Alert'
import { Avatar } from './Avatar'
import { DatePicker } from './DatePicker'
import { Divider } from './Divider'
import { Drawer } from './Drawer'
import { Empty } from './Empty'
import { Pagination } from './Pagination'
import { Popconfirm } from './Popconfirm'
import { Progress } from './Progress'
import { Skeleton } from './Skeleton'
import { Spinner } from './Spinner'
import { StatCard } from './StatCard'
import { Switch } from './Switch'
import { Tabs } from './Tabs'
import { Textarea } from './Textarea'
import { Timeline } from './Timeline'
import { Tooltip } from './Tooltip'

describe('Alert', () => {
  it('渲染标题、内容与关闭按钮', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Alert variant="warning" title="注意" onClose={onClose}>
        内容
      </Alert>
    )

    expect(screen.getByRole('alert')).toHaveClass('bg-warning-50')
    expect(screen.getByText('注意')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '关闭提示' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('Spinner / Skeleton / Empty', () => {
  it('Spinner 支持尺寸', () => {
    render(<Spinner size="lg" />)
    expect(screen.getByRole('status', { name: '加载中' })).toHaveClass('h-10')
  })

  it('Skeleton 三种形态', () => {
    const { rerender } = render(<Skeleton variant="text" rows={3} />)
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(3)
    rerender(<Skeleton variant="card" />)
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
    rerender(<Skeleton variant="table" rows={2} />)
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(2)
  })

  it('Empty 渲染标题/描述/操作', () => {
    render(
      <Empty title="暂无数据" description="稍后再试" action={<button type="button">新建</button>} />
    )
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
    expect(screen.getByText('稍后再试')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '新建' })).toBeInTheDocument()
  })
})

describe('Divider / Avatar / Timeline', () => {
  it('Divider 三个变体', () => {
    const { rerender } = render(<Divider />)
    expect(screen.getByRole('separator')).toHaveClass('h-px')
    rerender(<Divider orientation="vertical" />)
    expect(screen.getByRole('separator')).toHaveAttribute('aria-orientation', 'vertical')
    rerender(<Divider>或</Divider>)
    expect(screen.getByText('或')).toBeInTheDocument()
  })

  it('Avatar 无图时展示首字母，有图时渲染 img', () => {
    const { rerender } = render(<Avatar name="张三" size="lg" />)
    expect(screen.getByRole('img', { name: '张三' })).toHaveTextContent('张')
    rerender(<Avatar src="/avatar.png" name="张三" />)
    expect(screen.getByRole('img', { name: '张三' })).toHaveAttribute('src', '/avatar.png')
  })

  it('Timeline 渲染节点', () => {
    render(
      <Timeline
        items={[
          { title: '任务开始', time: '10:00', description: '已创建' },
          { title: '任务完成', status: 'success' },
        ]}
      />
    )
    expect(screen.getByText('任务开始')).toBeInTheDocument()
    expect(screen.getByText('10:00')).toBeInTheDocument()
    expect(screen.getByText('任务完成')).toBeInTheDocument()
  })
})

describe('Progress', () => {
  it('line 渲染进度与数值', () => {
    render(<Progress percent={85} showPercent />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '85')
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('circle 渲染环形进度', () => {
    render(<Progress variant="circle" percent={50} />)
    expect(screen.getByRole('img', { name: '进度 50%' })).toBeInTheDocument()
  })

  it('steps 渲染步骤', () => {
    render(<Progress variant="steps" steps={['上传', '清洗', '评估']} current={1} />)
    expect(screen.getByLabelText('步骤进度')).toBeInTheDocument()
    expect(screen.getByText('清洗')).toBeInTheDocument()
  })
})

describe('Switch / Textarea / DatePicker', () => {
  it('Switch 切换回调', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(<Switch label="自动清洗" checked={false} onCheckedChange={onCheckedChange} />)

    await user.click(screen.getByRole('switch', { name: '自动清洗' }))
    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('Textarea 回传值并展示错误/计数', () => {
    const onChange = vi.fn()
    const { rerender } = render(<Textarea value="" onChange={onChange} maxLength={100} />)
    expect(screen.getByText('0/100')).toBeInTheDocument()
    rerender(<Textarea value="abc" onChange={onChange} maxLength={100} error="不能为空" />)
    expect(screen.getByRole('alert')).toHaveTextContent('不能为空')
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true')
  })

  it('DatePicker 快捷范围与校验', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(<DatePicker value={{ start: '', end: '' }} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: '最近 7 天' }))
    expect(onChange).toHaveBeenCalledTimes(1)
    const range = onChange.mock.calls[0][0]
    expect(range.start).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(range.end).toMatch(/^\d{4}-\d{2}-\d{2}$/)

    rerender(<DatePicker value={{ start: '2026-10-10', end: '2026-10-01' }} onChange={onChange} />)
    expect(screen.getByRole('alert')).toHaveTextContent('开始日期不能晚于结束日期')
  })
})

describe('StatCard / Tabs / Pagination', () => {
  it('StatCard 展示数值与趋势', () => {
    render(
      <StatCard
        title="数据源"
        value={12}
        icon={<span>📊</span>}
        trend={{ value: 5, direction: 'up' }}
      />
    )
    expect(screen.getByText('数据源')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText(/5%/)).toBeInTheDocument()
  })

  it('Tabs 切换并回调', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Tabs
        items={[
          { key: 'all', label: '全部', count: 3 },
          { key: 'failed', label: '失败' },
        ]}
        defaultValue="all"
        onChange={onChange}
      />
    )

    expect(screen.getByRole('tab', { name: /全部/ })).toHaveAttribute('aria-selected', 'true')
    await user.click(screen.getByRole('tab', { name: '失败' }))
    expect(onChange).toHaveBeenCalledWith('failed')
  })

  it('Pagination 翻页与省略号', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Pagination current={1} pageSize={10} total={200} onChange={onChange} />)

    expect(screen.getByText('共 200 条')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '下一页' }))
    expect(onChange).toHaveBeenCalledWith(2, 10)
    expect(screen.getByRole('button', { name: '第 1 页' })).toHaveAttribute('aria-current', 'page')
  })
})

describe('Popconfirm / Tooltip / Drawer', () => {
  it('Popconfirm 确认与取消', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <Popconfirm
        title="确认删除？"
        description="不可恢复"
        onConfirm={onConfirm}
        onCancel={onCancel}
      >
        <button type="button">删除</button>
      </Popconfirm>
    )

    await user.click(screen.getByRole('button', { name: '删除' }))
    expect(await screen.findByText('确认删除？')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '取消' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('Tooltip 悬停展示内容', async () => {
    const user = userEvent.setup()
    render(
      <Tooltip content="提示内容">
        <button type="button">悬停</button>
      </Tooltip>
    )

    await user.hover(screen.getByRole('button', { name: '悬停' }))
    expect(await screen.findByText('提示内容')).toBeInTheDocument()
  })

  it('Drawer 渲染标题/内容/底部并关闭', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Drawer
        open
        onClose={onClose}
        title="新建条目"
        direction="right"
        footer={<button type="button">保存</button>}
      >
        表单内容
      </Drawer>
    )

    expect(screen.getByRole('dialog', { name: '新建条目' })).toBeInTheDocument()
    expect(screen.getByText('表单内容')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '关闭' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
