/**
 * 会话持久化（D-F05）：refresh_token 与用户信息按「记住我」分别写
 * localStorage / sessionStorage，key 统一为 `aiih.auth`。
 */
export const AUTH_STORAGE_KEY = 'aiih.auth'

function getStorages() {
  if (typeof window === 'undefined') return []
  return [window.localStorage, window.sessionStorage]
}

/**
 * 读取持久化会话。
 * @returns {{ user: Object, refreshToken: string, remember: boolean } | null}
 */
export function loadAuth() {
  for (const storage of getStorages()) {
    try {
      const raw = storage.getItem(AUTH_STORAGE_KEY)
      if (!raw) continue
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || !parsed.refreshToken) continue
      return {
        user: parsed.user || null,
        refreshToken: parsed.refreshToken,
        remember: Boolean(parsed.remember),
      }
    } catch {
      storage.removeItem(AUTH_STORAGE_KEY)
    }
  }
  return null
}

/**
 * 保存会话（先清两处，再按 remember 写入其一）。
 * @param {{ user: Object, refreshToken: string, remember?: boolean }} session
 */
export function saveAuth({ user, refreshToken, remember = false }) {
  if (typeof window === 'undefined') return
  clearAuth()
  const target = remember ? window.localStorage : window.sessionStorage
  target.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({ user: user || null, refreshToken, remember: Boolean(remember) })
  )
}

/** 清空持久化会话。 */
export function clearAuth() {
  for (const storage of getStorages()) {
    try {
      storage.removeItem(AUTH_STORAGE_KEY)
    } catch {
      // 忽略存储不可用（隐私模式等）
    }
  }
}
