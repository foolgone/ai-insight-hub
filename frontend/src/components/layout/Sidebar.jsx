import { useEffect } from 'react'
import clsx from 'clsx'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LuBookOpen,
  LuChevronLeft,
  LuChevronRight,
  LuClipboardCheck,
  LuDatabase,
  LuFileText,
  LuLayoutDashboard,
  LuWand2,
} from 'react-icons/lu'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { useUiStore } from '../../stores/uiStore'

const MENU_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', path: '/dashboard', icon: LuLayoutDashboard },
  { key: 'datasources', label: '数据源管理', path: '/data-sources', icon: LuDatabase },
  { key: 'cleaning', label: '数据清洗', path: '/data-cleaning', icon: LuWand2 },
  { key: 'quality', label: '质量评估', path: '/quality-assessment', icon: LuClipboardCheck },
  { key: 'knowledge', label: '知识库', path: '/knowledge-base', icon: LuBookOpen },
  { key: 'reports', label: '报告中心', path: '/reports', icon: LuFileText },
]

/**
 * 侧边栏（编辑部风格）：墨色底、等宽分组标签、朱砂色激活线。
 * 桌面 240/64px 两态，移动端抽屉。
 */
export function Sidebar() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const { pathname } = useLocation()
  const collapsed = useUiStore(state => state.sidebarCollapsed)
  const toggleSidebar = useUiStore(state => state.toggleSidebar)
  const mobileOpen = useUiStore(state => state.mobileSidebarOpen)
  const closeMobile = useUiStore(state => state.closeMobileSidebar)

  useEffect(() => {
    if (isMobile) closeMobile()
  }, [isMobile, pathname, closeMobile])

  const showLabel = isMobile || !collapsed
  const hiddenOnMobile = isMobile && !mobileOpen

  return (
    <>
      {isMobile && mobileOpen ? (
        <button
          type="button"
          aria-label="关闭菜单遮罩"
          className="fixed inset-0 z-30 bg-gray-900/50"
          onClick={closeMobile}
        />
      ) : null}
      <aside
        aria-label="侧边栏"
        aria-hidden={hiddenOnMobile ? true : undefined}
        inert={hiddenOnMobile ? '' : undefined}
        className={clsx(
          'flex shrink-0 flex-col border-r border-gray-900 bg-gray-900 text-gray-100 transition-transform duration-300',
          isMobile
            ? clsx(
                'fixed inset-y-0 left-0 z-40 w-64 shadow-xl',
                mobileOpen ? 'translate-x-0' : '-translate-x-full'
              )
            : collapsed
              ? 'w-16'
              : 'w-60'
        )}
      >
        <div
          className={clsx(
            'flex h-16 items-center gap-3 border-b border-white/10 px-4',
            !showLabel && 'justify-center px-0'
          )}
        >
          <div
            className="grid h-8 w-8 shrink-0 place-items-center border border-white/25 font-display text-[13px] leading-none text-gray-50"
            aria-hidden="true"
          >
            AI
          </div>
          {showLabel ? (
            <div className="min-w-0">
              <p className="truncate font-display text-[15px] leading-tight text-gray-50">
                AI Insight Hub
              </p>
              <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.2em] text-gray-500">
                Intelligence
              </p>
            </div>
          ) : null}
          {isMobile ? (
            <button
              type="button"
              aria-label="关闭菜单"
              className="ml-auto flex h-9 w-9 items-center justify-center text-gray-400 transition-colors hover:text-gray-50"
              onClick={closeMobile}
            >
              <LuChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        <nav aria-label="主菜单" className="flex-1 overflow-y-auto py-4">
          {showLabel ? (
            <p className="px-4 pb-2 font-mono text-[9px] uppercase tracking-[0.22em] text-gray-600">
              Workspace
            </p>
          ) : null}
          <div className="space-y-0.5 px-2">
            {MENU_ITEMS.map(item => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.key}
                  to={item.path}
                  end={item.path === '/dashboard'}
                  title={item.label}
                  className={({ isActive }) =>
                    clsx(
                      'relative flex h-10 items-center gap-3 px-3 text-[13px] transition-colors',
                      isActive
                        ? 'bg-white/[0.06] text-gray-50'
                        : 'text-gray-400 hover:bg-white/[0.04] hover:text-gray-100'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive ? (
                        <span
                          className="absolute inset-y-1 left-0 w-[2px] bg-primary-500"
                          aria-hidden="true"
                        />
                      ) : null}
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      {showLabel ? <span className="truncate">{item.label}</span> : null}
                    </>
                  )}
                </NavLink>
              )
            })}
          </div>
        </nav>

        {!isMobile ? (
          <div className="border-t border-white/10 p-2">
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}
              aria-expanded={!collapsed}
              className="flex h-9 w-full items-center justify-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-gray-500 transition-colors hover:text-gray-100"
            >
              {collapsed ? (
                <LuChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <>
                  <LuChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>收起</span>
                </>
              )}
            </button>
          </div>
        ) : null}
      </aside>
    </>
  )
}
