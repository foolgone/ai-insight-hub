import { create } from 'zustand'

/**
 * 凭据弹窗全局状态（D11：全局 428 拦截器 + 唯一 Modal Host）。
 *
 * `tab` 决定弹窗打开时落在哪一页：`llm`（模型 API Key）/ `asr`（语音转写）。
 * 组件内用 `useCredentialGate(state => state.openModal)`；
 * axios 拦截器（非 React 环境）用 `openCredentialModal(tab)`。
 */
export const useCredentialGate = create(set => ({
  open: false,
  tab: 'llm',
  openModal: (tab = 'llm') => set({ open: true, tab }),
  closeModal: () => set({ open: false }),
}))

/** 供 axios 拦截器调用：缺少哪类配置就打开对应标签页。 */
export function openCredentialModal(tab = 'llm') {
  useCredentialGate.setState({ open: true, tab })
}
