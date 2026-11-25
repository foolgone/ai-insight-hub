import { useAuthStore } from '../stores/authStore'

/**
 * 当前用户权限（A-7）。
 * @returns {{
 *   role: 'platform_admin'|'tenant_admin'|'user'|'viewer'|'admin'(legacy),
 *   isAdmin: boolean,
 *   isViewer: boolean,
 *   canWrite: boolean,
 *   can: (roles: string[]) => boolean,
 * }}
 */
export function usePermissions() {
  const user = useAuthStore(state => state.user)
  const role = user?.role || 'viewer'
  const isPlatformAdmin = role === 'platform_admin'
  const isTenantAdmin = role === 'tenant_admin'
  // 兼容旧 admin 文案/测试；后端新角色为 platform_admin / tenant_admin。
  const isAdmin = isPlatformAdmin || isTenantAdmin || role === 'admin'

  return {
    role,
    isPlatformAdmin,
    isTenantAdmin,
    isAdmin,
    isViewer: role === 'viewer',
    canWrite: role !== 'viewer',
    can: roles =>
      Array.isArray(roles) && (roles.includes(role) || (isAdmin && roles.includes('admin'))),
  }
}
