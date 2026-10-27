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
 * 侧边栏（04 §3.2）：桌面 240/64px 两态，移动端抽屉。
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
          className="fixed inset-0 z-30 bg-black/40"
          onClick={closeMobile}
        />
      ) : null}
      <aside
        aria-label="侧边栏"
        aria-hidden={hiddenOnMobile ? true : undefined}
        inert={hiddenOnMobile ? '' : undefined}
        className={clsx(
          'flex shrink-0 flex-col border-r border-gray-200 bg-white transition-transform duration-300',
          isMobile
            ? clsx(
                'fixed inset-y-0 left-0 z-40 w-60 shadow-lg',
                mobileOpen ? 'translate-x-0' : '-translate-x-full'
              )
            : collapsed
              ? 'w-16'
              : 'w-60'
        )}
      >
        <div
          className={clsx(
            'flex h-14 items-center gap-2 border-b border-gray-100 px-3 md:h-16',
            !showLabel && 'justify-center px-0'
          )}
        >
          <div
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary-600 text-xs font-bold text-white"
            aria-hidden="true"
          >
            AI
          </div>
          {showLabel ? (
            <span className="truncate text-sm font-semibold text-gray-900">AI Insight Hub</span>
          ) : null}
          {isMobile ? (
            <button
              type="button"
              aria-label="关闭菜单"
              className="ml-auto flex h-9 w-9 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100"
              onClick={closeMobile}
            >
              <LuChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        <nav aria-label="主菜单" className="flex-1 space-y-1 overflow-y-auto p-2">
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
                    'relative flex h-11 items-center gap-3 rounded-md px-3 text-sm transition-colors',
                    isActive
                      ? 'bg-primary-50 font-medium text-primary-600'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive ? (
                      <span
                        className="absolute inset-y-2 left-0 w-[3px] rounded-r bg-primary-600"
                        aria-hidden="true"
                      />
                    ) : null}
                    <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                    {showLabel ? <span className="truncate">{item.label}</span> : null}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>

        {!isMobile ? (
          <div className="border-t border-gray-100 p-2">
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}
              aria-expanded={!collapsed}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-md text-sm text-gray-500 hover:bg-gray-50"
            >
              {collapsed ? (
                <LuChevronRight className="h-4 w-4" aria-hidden="true" />
              ) : (
                <>
                  <LuChevronLeft className="h-4 w-4" aria-hidden="true" />
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
