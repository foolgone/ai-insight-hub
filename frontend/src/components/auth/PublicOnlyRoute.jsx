import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'

/**
 * 仅未登录可访问（如登录页）：已登录直接回 Dashboard（F-005）。
 */
export function PublicOnlyRoute() {
  const user = useAuthStore(state => state.user)
  return user ? <Navigate to="/dashboard" replace /> : <Outlet />
}
