// 自定义 render（与 docs/06-testing/04-前端测试规范.md §4.3 保持一致）
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * 渲染带 Provider 的组件树。
 * @param {React.ReactElement} ui 被测组件
 * @param {{ route?: string }} [options]
 */
export function renderWithProviders(ui, { route = '/' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 }, // 测试中不重试、不缓存
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}
