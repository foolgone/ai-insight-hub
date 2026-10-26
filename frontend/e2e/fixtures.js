/**
 * E2E 公共工具：凭据读取、UI 登录、API 会话、数据准备。
 */
import fs from 'node:fs'
import path from 'node:path'
import { expect, request } from '@playwright/test'

const AUTH_DIR = path.join(process.cwd(), 'e2e', '.auth')
const API_ORIGIN = (process.env.E2E_API_ORIGIN || 'http://localhost:8000').replace(/\/$/, '')
const API_PREFIX = process.env.E2E_API_PREFIX || '/api/v1'
export const API_BASE = `${API_ORIGIN}${API_PREFIX}`

export const CREDENTIALS = JSON.parse(
  fs.readFileSync(path.join(AUTH_DIR, 'credentials.json'), 'utf8')
)

/** 生成带时间戳/随机后缀的唯一名称，避免并行/重跑冲突。 */
export function uniqueName(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
}

/** 通过真实登录页完成登录（同时覆盖登录链路本身）。 */
export async function loginViaUi(page) {
  await page.goto('/login')
  await page.getByLabel('邮箱').fill(CREDENTIALS.email)
  await page.getByLabel('密码').fill(CREDENTIALS.password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
}

/** 用测试用户建立带 Bearer 的 API 会话（仅用于数据准备/清理，不替代 UI 断言）。 */
export async function apiSession() {
  const context = await request.newContext({ baseURL: API_ORIGIN })
  const login = await context.post(`${API_PREFIX}/auth/login`, { data: CREDENTIALS })
  if (!login.ok()) {
    throw new Error(`API 登录失败（${login.status()}）：${await login.text()}`)
  }
  const { access_token: accessToken } = await login.json()
  return {
    context,
    headers: { Authorization: `Bearer ${accessToken}` },
    close: () => context.dispose(),
  }
}

/** 通过 API 创建数据源（避免触发文件上传→清洗的 LLM 链路）。 */
export async function createDatasource(name, type = 'customer_service') {
  const session = await apiSession()
  try {
    const response = await session.context.post(`${API_PREFIX}/datasources`, {
      headers: session.headers,
      data: { name, type },
    })
    if (!response.ok()) {
      throw new Error(`创建数据源失败（${response.status()}）：${await response.text()}`)
    }
    return (await response.json()).id
  } finally {
    await session.close()
  }
}

/** 清理数据源（物理删除；失败忽略，避免影响用例结论）。 */
export async function deleteDatasource(id) {
  if (!id) return
  const session = await apiSession()
  try {
    await session.context.delete(`${API_PREFIX}/datasources/${id}?force=true`, {
      headers: session.headers,
    })
  } catch {
    // 用例内已删除时忽略
  } finally {
    await session.close()
  }
}

/** 在顶部「数据源选择器」中选择指定数据源。 */
export async function selectDatasource(page, name) {
  const trigger = page.getByRole('button', { name: '数据源选择器' })
  await trigger.click()
  await page.getByRole('option', { name: new RegExp(escapeRegExp(name)) }).click()
  await expect(trigger).toContainText(name)
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
