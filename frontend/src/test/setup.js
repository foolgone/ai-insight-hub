// 全局测试 setup（与 docs/06-testing/04-前端测试规范.md §4.2 保持一致）
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// 每个用例后卸载组件，避免 DOM 残留
afterEach(() => {
  cleanup()
})

// jsdom 未实现 matchMedia，必须 mock（响应式逻辑依赖它）
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(), // 兼容旧 API
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}
