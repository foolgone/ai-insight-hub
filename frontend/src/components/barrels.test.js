import { describe, expect, it } from 'vitest'
import * as Alert from './Alert'
import * as Avatar from './Avatar'
import * as Badge from './Badge'
import * as Button from './Button'
import * as Card from './Card'
import * as Chart from './Chart'
import * as Checkbox from './Checkbox'
import * as DatePicker from './DatePicker'
import * as Divider from './Divider'
import * as Drawer from './Drawer'
import * as Empty from './Empty'
import * as Input from './Input'
import * as Modal from './Modal'
import * as Pagination from './Pagination'
import * as Popconfirm from './Popconfirm'
import * as Progress from './Progress'
import * as Radio from './Radio'
import * as Select from './Select'
import * as Skeleton from './Skeleton'
import * as Spinner from './Spinner'
import * as StatCard from './StatCard'
import * as Switch from './Switch'
import * as Table from './Table'
import * as Tabs from './Tabs'
import * as Textarea from './Textarea'
import * as Timeline from './Timeline'
import * as Toast from './Toast'
import * as Tooltip from './Tooltip'

describe('组件 barrel 导出', () => {
  it('所有 index.js 均导出对应组件', () => {
    expect(typeof Alert.Alert).toBe('function')
    expect(typeof Avatar.Avatar).toBe('function')
    expect(typeof Badge.Badge).toBe('function')
    expect(Button.Button).toBeDefined()
    expect(typeof Card.Card).toBe('function')
    expect(typeof Chart.Chart).toBe('function')
    expect(typeof Checkbox.Checkbox).toBe('function')
    expect(typeof DatePicker.DatePicker).toBe('function')
    expect(typeof Divider.Divider).toBe('function')
    expect(typeof Drawer.Drawer).toBe('function')
    expect(typeof Empty.Empty).toBe('function')
    expect(typeof Input.Input).toBe('function')
    expect(typeof Modal.Modal).toBe('function')
    expect(typeof Pagination.Pagination).toBe('function')
    expect(typeof Popconfirm.Popconfirm).toBe('function')
    expect(typeof Progress.Progress).toBe('function')
    expect(typeof Radio.RadioGroup).toBe('function')
    expect(typeof Select.Select).toBe('function')
    expect(typeof Skeleton.Skeleton).toBe('function')
    expect(typeof Spinner.Spinner).toBe('function')
    expect(typeof StatCard.StatCard).toBe('function')
    expect(typeof Switch.Switch).toBe('function')
    expect(typeof Table.Table).toBe('function')
    expect(typeof Tabs.Tabs).toBe('function')
    expect(typeof Textarea.Textarea).toBe('function')
    expect(typeof Timeline.Timeline).toBe('function')
    expect(typeof Toast.ToastContainer).toBe('function')
    expect(typeof Tooltip.Tooltip).toBe('function')
  })
})
