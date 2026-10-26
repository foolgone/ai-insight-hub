import { expect, test } from '@playwright/test'
import { loginViaUi } from './fixtures'

const PAGES = [
  { menu: '数据源管理', heading: '数据源管理' },
  { menu: '数据清洗', heading: '数据清洗' },
  { menu: '质量评估', heading: '质量评估' },
  { menu: '知识库', heading: '知识库' },
  { menu: '报告中心', heading: '报告中心' },
]

test('侧边栏 5 个业务页可切换，标题与面包屑正确', async ({ page }) => {
  await loginViaUi(page)

  for (const item of PAGES) {
    await page.getByRole('navigation', { name: '主菜单' }).getByRole('link', { name: item.menu }).click()

    await expect(page.getByRole('heading', { name: item.heading })).toBeVisible()
    await expect(page.getByRole('navigation', { name: '面包屑' })).toContainText(item.heading)
  }

  // 回到 Dashboard：面包屑不应残留上一页
  await page.getByRole('navigation', { name: '主菜单' }).getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.getByRole('navigation', { name: '面包屑' })).toContainText('Dashboard')
})
