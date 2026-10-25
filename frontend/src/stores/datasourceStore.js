import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * 全局数据源上下文（D-F01）：只存 currentId，列表数据归 React Query。
 */
export const useDatasourceStore = create(
  persist(
    set => ({
      /** @type {string|null} */
      currentId: null,
      /** @param {string|null} id */
      setCurrentId: id => set({ currentId: id || null }),
      clearCurrentId: () => set({ currentId: null }),
    }),
    {
      name: 'aiih.datasource',
      partialize: state => ({ currentId: state.currentId }),
    }
  )
)
