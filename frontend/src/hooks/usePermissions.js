import { useAuthStore } from '../stores/authStore'

/**
 * 当前用户权限（A-7）。
 * @returns {{
 *   role: 'admin'|'user'|'viewer',
 *   isAdmin: boolean,
 *   isViewer: boolean,
 *   canWrite: boolean,
 *   can: (roles: string[]) => boolean,
 * }}
 */
export function usePermissions() {
  const user = useAuthStore(state => state.user)
  const role = user?.role || 'viewer'

  return {
    role,
    isAdmin: role === 'admin',
    isViewer: role === 'viewer',
    canWrite: role !== 'viewer',
    can: roles => Array.isArray(roles) && roles.includes(role),
  }
}
