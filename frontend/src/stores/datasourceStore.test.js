import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useDatasourceStore } from './datasourceStore'
import { useUiStore } from './uiStore'

describe('datasourceStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useDatasourceStore.setState({ currentId: null })
  })
  afterEach(() => {
    localStorage.clear()
    useDatasourceStore.setState({ currentId: null })
  })

  it('setCurrentId 更新并持久化', () => {
    useDatasourceStore.getState().setCurrentId('ds-1')

    expect(useDatasourceStore.getState().currentId).toBe('ds-1')
    expect(localStorage.getItem('aiih.datasource')).toContain('ds-1')
  })

  it('clearCurrentId 清空', () => {
    useDatasourceStore.getState().setCurrentId('ds-1')
    useDatasourceStore.getState().clearCurrentId()

    expect(useDatasourceStore.getState().currentId).toBeNull()
  })
})

describe('uiStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useUiStore.setState({ sidebarCollapsed: false, mobileSidebarOpen: false })
  })

  it('toggleSidebar 切换折叠并持久化', () => {
    useUiStore.getState().toggleSidebar()

    expect(useUiStore.getState().sidebarCollapsed).toBe(true)
    expect(localStorage.getItem('aiih.ui')).toContain('sidebarCollapsed')
  })

  it('移动端抽屉开关', () => {
    useUiStore.getState().openMobileSidebar()
    expect(useUiStore.getState().mobileSidebarOpen).toBe(true)

    useUiStore.getState().closeMobileSidebar()
    expect(useUiStore.getState().mobileSidebarOpen).toBe(false)
  })
})
