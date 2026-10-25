import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'

/**
 * 受保护路由（R-2）：未登录跳 /login 并带 returnUrl。
 */
export function ProtectedRoute() {
  const user = useAuthStore(state => state.user)
  const location = useLocation()

  if (!user) {
    const returnUrl = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?returnUrl=${returnUrl}`} replace />
  }

  return <Outlet />
}
