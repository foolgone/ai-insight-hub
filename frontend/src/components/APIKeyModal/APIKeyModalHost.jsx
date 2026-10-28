import { APIKeyModal } from './APIKeyModal'
import { useCredentialGate } from '../../lib/credentialGate'
import { useAuth } from '../../hooks/useAuth'
import { isDemoUser } from '../../lib/demoAccount'

/**
 * 全局唯一凭据弹窗宿主（D11）：挂在 AppLayout 上，
 * 由 `credentialGate` 状态驱动（用户菜单入口 / 428 拦截器）。
 */
export function APIKeyModalHost() {
  const open = useCredentialGate(state => state.open)
  const closeModal = useCredentialGate(state => state.closeModal)
  const { user } = useAuth()

  return <APIKeyModal open={open} onClose={closeModal} isDemo={isDemoUser(user)} />
}
