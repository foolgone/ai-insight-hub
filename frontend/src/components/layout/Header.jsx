import { LuMenu } from 'react-icons/lu'
import { useUiStore } from '../../stores/uiStore'
import { Breadcrumb } from './Breadcrumb'
import { DataSourceSelector } from './DataSourceSelector'
import { UserMenu } from './UserMenu'

/**
 * 顶部导航（03 §2.1）：Logo + 面包屑 + 数据源选择器插槽 + 用户菜单。
 * P2/F-106 在此接入全局数据源选择器。
 */
export function Header() {
  const openMobileSidebar = useUiStore(state => state.openMobileSidebar)

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-gray-200 bg-white px-3 md:h-16 md:px-4">
      <button
        type="button"
        aria-label="打开菜单"
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100 md:hidden"
        onClick={openMobileSidebar}
      >
        <LuMenu className="h-5 w-5" aria-hidden="true" />
      </button>

      <div className="flex shrink-0 items-center gap-2">
        <div
          className="grid h-9 w-9 place-items-center rounded-md bg-primary-600 text-sm font-bold text-white"
          aria-hidden="true"
        >
          AI
        </div>
        <span className="hidden text-base font-semibold text-gray-900 sm:inline">
          AI Insight Hub
        </span>
      </div>

      <div className="hidden min-w-0 flex-1 md:block">
        <Breadcrumb />
      </div>
      <div className="flex-1 md:hidden" />

      {/* 全局数据源选择器（D-F01 / F-106）：移动端仅图标，避免拥挤 */}
      <div data-testid="datasource-selector-slot" className="shrink-0">
        <DataSourceSelector />
      </div>

      <UserMenu />
    </header>
  )
}
