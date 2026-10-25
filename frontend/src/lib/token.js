/**
 * access_token 的内存存储（D-F05：不落 Web Storage）。
 * axios 拦截器与 authStore 共用，避免循环依赖。
 */
let accessToken = null

/**
 * 写入 access_token。
 * @param {string|null} token
 */
export function setAccessToken(token) {
  accessToken = token || null
}

/**
 * 读取 access_token。
 * @returns {string|null}
 */
export function getAccessToken() {
  return accessToken
}

/** 清空内存中的 access_token。 */
export function clearAccessToken() {
  accessToken = null
}
