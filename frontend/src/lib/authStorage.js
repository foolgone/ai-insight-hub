/**
 * 会话持久化（D-F05 + T4）。
 *
 * - 只持久化「用户信息 + 记住我」；access_token 只在内存（`lib/token.js`）；
 * - refresh token 由后端写入 **HttpOnly Cookie**，JS 不可读，因此不落 Web Storage。
 *   「记住我」只决定用户信息写 localStorage 还是 sessionStorage。
 */
export const AUTH_STORAGE_KEY = 'aiih.auth'

function getStorages() {
  if (typeof window === 'undefined') return []
  return [window.localStorage, window.sessionStorage]
}

/**
 * 读取持久化会话。
 * @returns {{ user: Object, remember: boolean } | null}
 */
export function loadAuth() {
  for (const storage of getStorages()) {
    try {
      const raw = storage.getItem(AUTH_STORAGE_KEY)
      if (!raw) continue
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || !parsed.user) continue
      return {
        user: parsed.user,
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
 * @param {{ user: Object, remember?: boolean }} session
 */
export function saveAuth({ user, remember = false }) {
  if (typeof window === 'undefined') return
  clearAuth()
  const target = remember ? window.localStorage : window.sessionStorage
  target.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({ user: user || null, remember: Boolean(remember) })
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
