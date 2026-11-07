import { LuMenu } from 'react-icons/lu'
import { useUiStore } from '../../stores/uiStore'
import { Breadcrumb } from './Breadcrumb'
import { DataSourceSelector } from './DataSourceSelector'
import { UserMenu } from './UserMenu'

/**
 * 顶部导航（编辑部风格）：纸色半透明页头、等宽面包屑、右侧数据源与用户菜单。
 */
export function Header() {
  const openMobileSidebar = useUiStore(state => state.openMobileSidebar)

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-gray-200 bg-gray-50/90 px-3 backdrop-blur md:h-16 md:px-8">
      <button
        type="button"
        aria-label="打开菜单"
        className="flex h-9 w-9 shrink-0 items-center justify-center text-gray-600 transition-colors hover:text-gray-900 md:hidden"
        onClick={openMobileSidebar}
      >
        <LuMenu className="h-5 w-5" aria-hidden="true" />
      </button>

      <div className="flex shrink-0 items-center gap-2 md:hidden">
        <div
          className="grid h-8 w-8 place-items-center border border-gray-900 font-display text-[12px] leading-none text-gray-900"
          aria-hidden="true"
        >
          AI
        </div>
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
