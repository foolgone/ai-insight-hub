import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { PageLoading } from '../common/PageLoading'
import { APIKeyModalHost } from '../APIKeyModal'

/**
 * 应用主布局（03 §1.1）：Header + Sidebar + 内容区 + 全局凭据弹窗宿主（BYOK D11）。
 *
 * Suspense 必须放在内容区内部：路由懒加载时只替换 <Outlet />，
 * 侧栏与页头保持挂载，避免整页闪空（顶层 Suspense 会把布局一起卸载）。
 */
export function AppLayout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-6 md:px-8 md:py-10 lg:px-10">
            <Suspense
              fallback={
                <div className="min-h-[60vh]">
                  <PageLoading label="正在加载页面..." />
                </div>
              }
            >
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
      <APIKeyModalHost />
    </div>
  )
}
