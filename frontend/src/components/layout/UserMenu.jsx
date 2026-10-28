import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useNavigate } from 'react-router-dom'
import { LuKey, LuLogOut } from 'react-icons/lu'
import { useAuth } from '../../hooks/useAuth'
import { useCredentialStatusQuery } from '../../hooks/useLlmCredential'
import { useCredentialGate } from '../../lib/credentialGate'
import { notify } from '../../lib/toast'

const ROLE_LABELS = {
  admin: '管理员',
  user: '普通用户',
  viewer: '访客',
}

/**
 * 用户头像菜单（F-104/F-106）：显示用户信息与退出登录。
 */
export function UserMenu() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const openCredentialModal = useCredentialGate(state => state.openModal)
  const { data: credentialStatus } = useCredentialStatusQuery({ enabled: Boolean(user) })

  if (!user) return null

  const displayName = user.name || user.email
  const roleLabel = ROLE_LABELS[user.role] || user.role
  // 后端关闭 BYOK 时隐藏入口（默认显示，功能由后端守门兜底）
  const showCredentialEntry = credentialStatus?.byok_enabled !== false

  const handleLogout = async () => {
    await logout()
    notify.success('已退出登录')
    navigate('/login', { replace: true })
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="打开用户菜单"
          className="flex shrink-0 items-center gap-2 rounded-full px-1 py-1 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
        >
          <span
            className="grid h-8 w-8 place-items-center rounded-full bg-primary-100 text-xs font-medium text-primary-700"
            aria-hidden="true"
          >
            {displayName.slice(0, 1).toUpperCase()}
          </span>
          <span className="hidden max-w-32 truncate text-sm text-gray-700 md:inline">
            {displayName}
          </span>
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          sideOffset={8}
          align="end"
          className="z-50 min-w-48 rounded-md border border-gray-200 bg-white p-1 shadow-lg focus:outline-none"
        >
          <div className="border-b border-gray-100 px-3 py-2">
            <p className="truncate text-sm font-medium text-gray-900">{displayName}</p>
            <p className="mt-0.5 text-xs text-gray-500">{roleLabel}</p>
            {user.email ? (
              <p className="mt-0.5 truncate text-xs text-gray-400">{user.email}</p>
            ) : null}
          </div>
          {showCredentialEntry ? (
            <DropdownMenu.Item
              onSelect={openCredentialModal}
              className="flex cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-gray-700 outline-none focus:bg-gray-100"
            >
              <LuKey className="h-4 w-4" aria-hidden="true" />
              API Key 管理
            </DropdownMenu.Item>
          ) : null}
          <DropdownMenu.Item
            onSelect={handleLogout}
            className="flex cursor-pointer items-center gap-2 rounded px-3 py-2 text-sm text-error-600 outline-none focus:bg-error-50"
          >
            <LuLogOut className="h-4 w-4" aria-hidden="true" />
            退出登录
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
