import { describe, expect, it } from 'vitest'
import * as Badge from '../components/Badge'
import * as Button from '../components/Button'
import * as Card from '../components/Card'
import * as Checkbox from '../components/Checkbox'
import * as Input from '../components/Input'
import * as Modal from '../components/Modal'
import * as Radio from '../components/Radio'
import * as Select from '../components/Select'
import * as Table from '../components/Table'
import * as Toast from '../components/Toast'

describe('组件 barrel 导出', () => {
  it('所有 index.js 均导出对应组件', () => {
    expect(typeof Badge.Badge).toBe('function')
    expect(typeof Button.Button).toBe('function')
    expect(typeof Card.Card).toBe('function')
    expect(typeof Checkbox.Checkbox).toBe('function')
    expect(typeof Input.Input).toBe('function')
    expect(typeof Modal.Modal).toBe('function')
    expect(typeof Radio.RadioGroup).toBe('function')
    expect(typeof Select.Select).toBe('function')
    expect(typeof Table.Table).toBe('function')
    expect(typeof Toast.ToastContainer).toBe('function')
  })
})
