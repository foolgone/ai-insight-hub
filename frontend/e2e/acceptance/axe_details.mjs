// 一次性诊断：抓取 axe 每条违规的节点选择器（用于定位 a11y 修复点）
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'
import { AxeBuilder } from '@axe-core/playwright'

const APP = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000/api/v1'
const suffix = Date.now().toString(36)
const email = `axe-${suffix}@example.com`
const password = 'Axe123456'

const reg = await fetch(`${API}/auth/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password, name: 'axe 用户' }),
})
if (![201, 409].includes(reg.status)) throw new Error(`register ${reg.status}`)

const browser = await chromium.launch({ channel: 'msedge' })
const context = await browser.newContext({ baseURL: APP, viewport: { width: 1280, height: 800 } })
const page = await context.newPage()
await page.goto('/login')
await page.getByLabel('邮箱').fill(email)
await page.getByLabel('密码').fill(password)
await page.getByRole('button', { name: '登录', exact: true }).click()
await page.getByRole('heading', { name: 'Dashboard' }).waitFor()

const pages = ['/dashboard', '/data-sources', '/data-cleaning', '/quality-assessment', '/knowledge-base', '/reports']
const details = []
for (const target of pages) {
  await page.goto(target)
  await page.waitForTimeout(1200)
  const analysis = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  for (const violation of analysis.violations) {
    for (const node of violation.nodes) {
      details.push({
        page: target,
        id: violation.id,
        impact: violation.impact,
        target: node.target,
        html: node.html?.slice(0, 200),
        failure: node.failureSummary?.slice(0, 200),
      })
    }
  }
}
fs.writeFileSync(
  path.resolve(process.cwd(), '..', 'ops', 'acceptance', 'axe-details.json'),
  JSON.stringify(details, null, 2)
)
const grouped = {}
for (const item of details) {
  grouped[item.id] = grouped[item.id] || []
  if (grouped[item.id].length < 6) grouped[item.id].push(item)
}
for (const [id, items] of Object.entries(grouped)) {
  console.log(`\n=== ${id} (${details.filter(d => d.id === id).length}) ===`)
  for (const item of items) {
    console.log(`- ${item.page} | ${JSON.stringify(item.target)}`)
    console.log(`  html: ${item.html}`)
    if (item.failure) console.log(`  why: ${item.failure}`)
  }
}
await browser.close()
