import { defineConfig } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

/**
 * E2E 配置（T1）：对**真实前端 + 真实后端 + 真实 PG/Redis** 跑浏览器用例。
 *
 * 前置：
 * 1. 后端 `uvicorn app.main:app --port 8000`（develop 环境 .env 指向 VM 的 PG/Redis）；
 * 2. 前端 `npm run dev`（5173，/api 代理到 8000）；
 * 3. 首次运行前 `npx playwright install chromium`。
 *
 * 运行：`npm run test:e2e` / `npm run test:e2e:headed` / `npm run test:e2e:ui`
 * 说明：E2E 强调真实链路，不 mock API；涉及 LLM 的清洗/评估/报告生成不在本套用例中。
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  globalSetup: './e2e/global-setup.js',
  use: {
    baseURL: BASE_URL,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        // 本地默认用系统已安装的 Edge（免下载 Chromium）；CI 设 E2E_BROWSER_CHANNEL=chromium
        channel: process.env.E2E_BROWSER_CHANNEL || 'msedge',
        locale: 'zh-CN',
        viewport: { width: 1440, height: 900 },
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'off',
      },
    },
  ],
})
