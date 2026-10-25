import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useUiStore = create(
  persist(
    set => ({
      /** 桌面端侧栏是否折叠（64px） */
      sidebarCollapsed: false,
      /** 移动端抽屉是否打开 */
      mobileSidebarOpen: false,

      toggleSidebar: () => set(state => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      /** @param {boolean} collapsed */
      setSidebarCollapsed: collapsed => set({ sidebarCollapsed: collapsed }),
      openMobileSidebar: () => set({ mobileSidebarOpen: true }),
      closeMobileSidebar: () => set({ mobileSidebarOpen: false }),
    }),
    {
      name: 'aiih.ui',
      partialize: state => ({ sidebarCollapsed: state.sidebarCollapsed }),
    }
  )
)
