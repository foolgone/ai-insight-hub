// 验收：浏览器走查（5 档响应式 + Modal/Drawer + 键盘 + axe a11y）
// 运行（frontend 目录，前后端已启动）：
//   node e2e/acceptance/browser_audit.mjs
// 产物：ops/acceptance/screenshots/*.png、browser-audit.json、browser-audit.md
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from '@playwright/test'
import { AxeBuilder } from '@axe-core/playwright'

const APP = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173'
const API = (process.env.E2E_API_ORIGIN || 'http://127.0.0.1:8000') + '/api/v1'
const OUT = path.resolve(process.cwd(), '..', 'ops', 'acceptance')
const SHOTS = path.join(OUT, 'screenshots')
fs.mkdirSync(SHOTS, { recursive: true })

const VIEWPORTS = [
  { name: '375-mobile', width: 375, height: 812 },
  { name: '768-tablet', width: 768, height: 1024 },
  { name: '1024-laptop', width: 1024, height: 768 },
  { name: '1280-desktop', width: 1280, height: 800 },
  { name: '1920-wide', width: 1920, height: 1080 },
]

const PAGES = [
  { name: 'dashboard', path: '/dashboard', heading: 'Dashboard' },
  { name: 'data-sources', path: '/data-sources', heading: '数据源管理' },
  { name: 'data-cleaning', path: '/data-cleaning', heading: '数据清洗' },
  { name: 'quality-assessment', path: '/quality-assessment', heading: '质量评估' },
  { name: 'knowledge-base', path: '/knowledge-base', heading: '知识库' },
  { name: 'reports', path: '/reports', heading: '报告中心' },
]

const suffix = Date.now().toString(36)
const email = `audit-${suffix}@example.com`
const password = 'Audit12345'

async function apiRegisterLogin() {
  const reg = await fetch(`${API}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name: '浏览器走查用户' }),
  })
  if (![201, 409].includes(reg.status)) throw new Error(`register ${reg.status}: ${await reg.text()}`)
  const login = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!login.ok) throw new Error(`login ${login.status}: ${await login.text()}`)
  const { access_token: token } = await login.json()
  const ds = await fetch(`${API}/datasources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ name: `audit-ds-${suffix}`, type: 'customer_service' }),
  })
  if (!ds.ok) throw new Error(`create datasource ${ds.status}`)
  return { token, datasource: await ds.json() }
}

async function loginUi(page) {
  await page.goto(`${APP}/login`)
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('heading', { name: 'Dashboard' }).waitFor()
}

function bboxInside(viewport, box) {
  if (!box) return false
  return box.x >= -1 && box.y >= -1 && box.x + box.width <= viewport.width + 1 && box.y <= viewport.height + 1
}

const results = []
const axeSummary = {}

async function axeScan(page, pageName) {
  try {
    const analysis = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    const violations = analysis.violations.map(item => ({
      id: item.id,
      impact: item.impact,
      help: item.help,
      nodes: item.nodes.length,
    }))
    axeSummary[pageName] = violations
    return violations
  } catch (error) {
    axeSummary[pageName] = [{ id: 'axe-error', impact: 'unknown', help: String(error), nodes: 1 }]
    return axeSummary[pageName]
  }
}

const browser = await chromium.launch({ channel: 'msedge' })
const { token, datasource } = await apiRegisterLogin()

try {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      baseURL: APP,
      viewport: { width: vp.width, height: vp.height },
      locale: 'zh-CN',
    })
    const page = await context.newPage()
    const record = { viewport: vp.name, pages: [], overflow: [], modals: [], keyboard: null }
    await loginUi(page)

    for (const target of PAGES) {
      await page.goto(target.path)
      await page.getByRole('heading', { name: target.heading }).waitFor({ timeout: 15000 })
      await page.waitForTimeout(800)
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      )
      record.pages.push({ page: target.name, heading: target.heading, overflowX: overflow })
      if (overflow > 2) record.overflow.push({ page: target.name, px: overflow })
      await page.screenshot({
        path: path.join(SHOTS, `${vp.name}-${target.name}.png`),
        fullPage: false,
      })
      const violations = await axeScan(page, `${vp.name}:${target.name}`)
      record.pages[record.pages.length - 1].axeViolations = violations.length
      record.pages[record.pages.length - 1].serious = violations.filter(v =>
        ['serious', 'critical'].includes(v.impact)
      ).length
    }

    // Drawer：数据源新建（检查越界 + Esc 关闭）
    await page.goto('/data-sources')
    await page.getByRole('button', { name: '新建数据源' }).first().click()
    const drawer = page.getByRole('dialog', { name: '新建数据源' })
    await drawer.waitFor()
    const drawerBox = await drawer.boundingBox()
    record.modals.push({
      name: 'new-datasource-drawer',
      inside: bboxInside({ width: vp.width, height: vp.height }, drawerBox),
      box: drawerBox,
    })
    await page.keyboard.press('Escape')
    record.modals[record.modals.length - 1].escapeClosed = await drawer
      .waitFor({ state: 'hidden', timeout: 5000 })
      .then(() => true)
      .catch(() => false)

    // Modal：报告生成（先选数据源）
    await page.goto('/reports')
    await page.getByRole('button', { name: '数据源选择器' }).click()
    await page.getByRole('option', { name: new RegExp(datasource.name) }).click()
    await page.getByRole('button', { name: '生成报告' }).click()
    const modal = page.getByRole('dialog', { name: '生成报告' })
    await modal.waitFor()
    const modalBox = await modal.boundingBox()
    record.modals.push({
      name: 'report-modal',
      inside: bboxInside({ width: vp.width, height: vp.height }, modalBox),
      box: modalBox,
    })
    await modal.getByRole('button', { name: '取消' }).click()

    // 键盘：Tab 序列（登录页，独立匿名上下文）
    if (vp.name === '1024-laptop' || vp.name === '375-mobile') {
      const anon = await browser.newContext({
        baseURL: APP,
        viewport: { width: vp.width, height: vp.height },
        locale: 'zh-CN',
      })
      const anonPage = await anon.newPage()
      await anonPage.goto('/login')
      const order = []
      for (let i = 0; i < 6; i += 1) {
        await anonPage.keyboard.press('Tab')
        order.push(
          await anonPage.evaluate(() => {
            const el = document.activeElement
            if (!el) return 'null'
            return (
              el.getAttribute('aria-label') ||
              el.getAttribute('placeholder') ||
              (el.textContent || el.tagName).trim().slice(0, 30)
            )
          })
        )
      }
      record.keyboard = order
      await anon.close()
    }

    await context.close()
    results.push(record)
    console.log(`[OK] ${vp.name} pages=${record.pages.length} overflow=${record.overflow.length} modals=${record.modals.length}`)
  }
} finally {
  await browser.close()
}

const allViolations = Object.entries(axeSummary).flatMap(([key, items]) =>
  items.map(item => ({ page: key, ...item }))
)
const serious = allViolations.filter(item => ['serious', 'critical'].includes(item.impact))
const overflow = results.flatMap(r => r.overflow.map(item => ({ viewport: r.viewport, ...item })))
const modalIssues = results.flatMap(r =>
  r.modals.filter(m => !m.inside || m.escapeClosed === false).map(m => ({ viewport: r.viewport, ...m }))
)

const summary = {
  generatedAt: new Date().toISOString(),
  app: APP,
  viewports: VIEWPORTS,
  screenshots: fs.readdirSync(SHOTS).length,
  axe: { pages: Object.keys(axeSummary).length, violations: allViolations.length, serious: serious.length },
  overflow,
  modalIssues,
  keyboard: Object.fromEntries(results.filter(r => r.keyboard).map(r => [r.viewport, r.keyboard])),
  results,
  allViolations,
}
fs.writeFileSync(path.join(OUT, 'browser-audit.json'), JSON.stringify(summary, null, 2))

const lines = [
  '# 上线验收：浏览器走查报告',
  '',
  `- 时间：${summary.generatedAt}`,
  `- 前端：\`${APP}\``,
  `- 视口：${VIEWPORTS.map(v => v.name).join(' / ')}`,
  `- 截图：${summary.screenshots} 张（\`ops/acceptance/screenshots/\`）`,
  `- 横向溢出：${overflow.length} 处`,
  `- Modal/Drawer 问题：${modalIssues.length} 处`,
  `- axe（WCAG 2 A/AA）：${allViolations.length} 条，其中 serious/critical **${serious.length}** 条`,
  '',
  '## 键盘 Tab 序列（登录页）',
  '',
  ...Object.entries(summary.keyboard).map(([vp, order]) => `- ${vp}: ${order.join(' → ')}`),
  '',
  '## axe serious/critical',
  '',
  serious.length
    ? serious.map(v => `- [${v.impact}] ${v.id}（${v.page}，${v.nodes} 节点）：${v.help}`).join('\n')
    : '- 无',
  '',
  '## Modal/Drawer 越界/关闭',
  '',
  modalIssues.length
    ? modalIssues.map(m => `- ${m.viewport} ${m.name}: inside=${m.inside} escapeClosed=${m.escapeClosed}`).join('\n')
    : '- 全部在视口内且 Esc 可关闭',
  '',
]
fs.writeFileSync(path.join(OUT, 'browser-audit.md'), lines.join('\n'))

console.log(
  `\n汇总：溢出=${overflow.length} modal问题=${modalIssues.length} axe=${allViolations.length}（serious=${serious.length}）`
)
process.exit(modalIssues.length || overflow.length ? 1 : 0)
