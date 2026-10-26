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

/**
 * 预热路由的懒加载模块（router.jsx 中 `lazy(() => import(...))`）。
 *
 * 背景：全量并行跑测试时，多个 worker 会争抢 Vite 模块转换，首次 import 一个
 * 较重页面（如 Dashboard → recharts）可能超过 findBy* 的超时，导致用例偶发
 * 停在 Suspense fallback。在 beforeAll 里先预热一次，后续懒加载即命中缓存。
 *
 * 用法：`beforeAll(preloadRoutes, 30000)`
 */
export async function preloadRoutes() {
  await Promise.all([
    import('../pages/Login'),
    import('../pages/Dashboard'),
    import('../pages/DataSources'),
    import('../pages/DataCleaning'),
    import('../pages/QualityAssessment'),
    import('../pages/QualityAssessment/Detail'),
    import('../pages/KnowledgeBase'),
    import('../pages/Reports'),
    import('../pages/NotFound'),
  ])
}
