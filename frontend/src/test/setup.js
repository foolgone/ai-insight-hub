// 全局测试 setup（与 docs/06-testing/04-前端测试规范.md §4.2 保持一致）
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// 每个用例后卸载组件，避免 DOM 残留
afterEach(() => {
  cleanup()
})

// jsdom 未实现 matchMedia，必须提供实现（响应式逻辑依赖它）。
// 注意：这里用普通函数而非 vi.fn，避免 vitest restoreMocks 后 mock 失效。
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: query => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {}, // 兼容旧 API
      removeListener() {},
      dispatchEvent() {
        return false
      },
    }),
  })
}
