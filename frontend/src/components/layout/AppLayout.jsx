import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { APIKeyModalHost } from '../APIKeyModal'

/**
 * 应用主布局（03 §1.1）：Header + Sidebar + 内容区 + 全局凭据弹窗宿主（BYOK D11）。
 */
export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-6 md:px-8 md:py-10 lg:px-10">
            <Outlet />
          </div>
        </main>
      </div>
      <APIKeyModalHost />
    </div>
  )
}
