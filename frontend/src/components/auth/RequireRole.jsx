import { usePermissions } from '../../hooks/usePermissions'

/**
 * 角色门禁（A-7）：角色不满足时渲染无权限提示。
 * @param {{ roles: string[], children: React.ReactNode }} props
 */
export function RequireRole({ roles, children }) {
  const { can } = usePermissions()

  if (!can(roles)) {
    return (
      <div
        role="alert"
        className="rounded-md border border-error-200 bg-error-50 p-4 text-sm text-error-700"
      >
        无权限访问该页面
      </div>
    )
  }

  return children
}
