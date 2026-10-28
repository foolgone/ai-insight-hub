import { beforeEach, describe, expect, it } from 'vitest'
import { openCredentialModal, useCredentialGate } from './credentialGate'

describe('credentialGate', () => {
  beforeEach(() => {
    useCredentialGate.setState({ open: false })
  })

  it('openModal / closeModal 切换状态', () => {
    useCredentialGate.getState().openModal()
    expect(useCredentialGate.getState().open).toBe(true)

    useCredentialGate.getState().closeModal()
    expect(useCredentialGate.getState().open).toBe(false)
  })

  it('openCredentialModal 供 axios 拦截器（非 React）调用', () => {
    openCredentialModal()
    expect(useCredentialGate.getState().open).toBe(true)
  })
})
