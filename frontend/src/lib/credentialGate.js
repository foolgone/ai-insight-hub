import { create } from 'zustand'

/**
 * 凭据弹窗全局状态（D11：全局 428 拦截器 + 唯一 Modal Host）。
 *
 * 组件内用 `useCredentialGate(state => state.openModal)`；
 * axios 拦截器（非 React 环境）用 `openCredentialModal()`。
 */
export const useCredentialGate = create(set => ({
  open: false,
  openModal: () => set({ open: true }),
  closeModal: () => set({ open: false }),
}))

/** 供 axios 拦截器调用：用户触发 AI 操作但未配置 Key（428）时弹出设置弹窗。 */
export function openCredentialModal() {
  useCredentialGate.setState({ open: true })
}
