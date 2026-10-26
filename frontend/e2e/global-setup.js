/**
 * E2E 全局前置：确认前后端可达，注册唯一测试用户并写入凭据。
 *
 * - 测试用户：`e2e-<timestamp>@example.com`（每个 run 唯一，避免与开发数据冲突）；
 * - 凭据写入 `e2e/.auth/credentials.json`（已 gitignore）；
 * - 不依赖 storageState：认证由用例通过真实登录页完成（覆盖登录链路本身）。
 */
import fs from 'node:fs'
import path from 'node:path'
import { request } from '@playwright/test'

const API_ORIGIN = (process.env.E2E_API_ORIGIN || 'http://localhost:8000').replace(/\/$/, '')
const API_PREFIX = process.env.E2E_API_PREFIX || '/api/v1'
const API_BASE = `${API_ORIGIN}${API_PREFIX}`
const APP_BASE = process.env.E2E_BASE_URL || 'http://localhost:5173'
const AUTH_DIR = path.join(process.cwd(), 'e2e', '.auth')

async function assertReachable(label, url) {
  const context = await request.newContext()
  try {
    const response = await context.get(url)
    if (!response.ok()) {
      throw new Error(
        `${label} 不可用（${url} 返回 ${response.status()}）。请先启动前后端：` +
          '后端 uvicorn app.main:app --port 8000，前端 npm run dev。'
      )
    }
  } finally {
    await context.dispose()
  }
}

export default async function globalSetup() {
  fs.mkdirSync(AUTH_DIR, { recursive: true })
  await assertReachable('后端', `${API_BASE}/health`)
  await assertReachable('前端', APP_BASE)

  const email = `e2e-${Date.now()}@example.com`
  const password = 'E2ePass123!'
  const api = await request.newContext({ baseURL: API_ORIGIN })
  try {
    const register = await api.post(`${API_PREFIX}/auth/register`, {
      data: { email, password, name: 'E2E 测试用户' },
    })
    if (![201, 409].includes(register.status())) {
      throw new Error(`测试用户注册失败（${register.status()}）：${await register.text()}`)
    }
    const login = await api.post(`${API_PREFIX}/auth/login`, { data: { email, password } })
    if (!login.ok()) {
      throw new Error(`测试用户登录失败（${login.status()}）：${await login.text()}`)
    }
  } finally {
    await api.dispose()
  }

  fs.writeFileSync(
    path.join(AUTH_DIR, 'credentials.json'),
    JSON.stringify({ email, password }, null, 2),
    'utf8'
  )
  // eslint-disable-next-line no-console
  console.log(`[e2e] 测试用户已就绪：${email}`)
}
